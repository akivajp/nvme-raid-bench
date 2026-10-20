"""計測中の NVMe 温度の記録と、SMART の温度関連カウンタの取得。"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


def nvme_hwmon_paths() -> dict[str, Path]:
    """コントローラ名 (nvme0 等) → 温度 (Composite) の sysfs パス。root 権限は不要。"""
    out: dict[str, Path] = {}
    for name_file in sorted(Path("/sys/class/hwmon").glob("hwmon*/name")):
        if name_file.read_text().strip() != "nvme":
            continue
        hwmon = name_file.parent
        ctrl = (hwmon / "device").resolve().name  # 例: nvme0
        out[ctrl] = hwmon / "temp1_input"
    return out


def dirty_writeback_mib() -> float:
    """ページキャッシュのうち、ディスクへの書き出し待ち (Dirty) と書き出し中 (Writeback) の合計 (MiB)。

    O_DIRECT の書き込み中にここが増えるなら、実際にはページキャッシュを経由している (バッファ書き込みへのフォールバック)。
    """
    total_kib = 0
    with open("/proc/meminfo") as f:
        for line in f:
            key, _, rest = line.partition(":")
            if key in ("Dirty", "Writeback"):
                total_kib += int(rest.split()[0])
    return total_kib / 1024


class TempMonitor:
    """別スレッドで一定間隔ごとに全 NVMe の温度とページキャッシュの書き出し待ちを読み、時系列と最大値を保持する。

    with 文で使う。抜けたときに samples (経過秒, {nvme0: ℃, ..., "dirty_wb_mib": MiB}) と max_temps が確定する。
    """

    def __init__(self, interval: float = 1.0) -> None:
        self.interval = interval
        self.paths = nvme_hwmon_paths()
        self.samples: list[tuple[float, dict[str, float]]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._t0 = 0.0

    def read_once(self) -> dict[str, float]:
        """現在の温度 (℃) を読む。"""
        temps: dict[str, float] = {}
        for ctrl, path in self.paths.items():
            try:
                temps[ctrl] = int(path.read_text()) / 1000
            except OSError:
                pass
        temps["dirty_wb_mib"] = dirty_writeback_mib()
        return temps

    def _loop(self) -> None:
        # 計測区間の端を落とさないよう、開始直後と終了直前にも記録する
        while not self._stop.is_set():
            self.samples.append((time.monotonic() - self._t0, self.read_once()))
            self._stop.wait(self.interval)
        self.samples.append((time.monotonic() - self._t0, self.read_once()))

    def __enter__(self) -> TempMonitor:
        self._t0 = time.monotonic()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()

    @property
    def max_temps(self) -> dict[str, float]:
        """デバイスごとの最高温度 (℃)。"""
        out: dict[str, float] = {}
        for _, temps in self.samples:
            for k, v in temps.items():
                if k.startswith("nvme"):
                    out[k] = max(out.get(k, v), v)
        return out

    @property
    def max_dirty_wb_mib(self) -> float:
        """計測中の Dirty + Writeback の最大値 (MiB)。"""
        return max((t.get("dirty_wb_mib", 0.0) for _, t in self.samples), default=0.0)


# SMART の温度関連の項目 (nvme-cli 2.x の JSON のキー名)
_THERMAL_KEYS = (
    "temperature",
    "warning_temp_time",
    "critical_comp_time",
    "thm_temp1_trans_count",
    "thm_temp2_trans_count",
    "thm_temp1_total_time",
    "thm_temp2_total_time",
)


def smart_thermal(ctrl: str) -> dict[str, Any]:
    """nvme smart-log から温度とサーマルスロットリングの累計を取る (要 sudo。失敗時は空)。

    thm_temp1/2 は、コントローラが温度により性能を落とした回数 (trans_count) と累計秒数 (total_time)。
    計測の前後の差を見れば、計測中にスロットリングが起きたかが分かる。
    """
    try:
        out = subprocess.run(
            ["sudo", "-n", "nvme", "smart-log", f"/dev/{ctrl}", "--output-format=json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    data = json.loads(out)
    return {k: data[k] for k in _THERMAL_KEYS if k in data}


def smart_thermal_all(ctrls: list[str]) -> dict[str, dict[str, Any]]:
    """複数コントローラ分の smart_thermal。"""
    return {c: smart_thermal(c) for c in ctrls}
