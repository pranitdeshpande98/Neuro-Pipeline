from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EdfHeader:
    n_channels: int
    n_records: int
    record_duration_s: float
    sfreq_hz: float

    @property
    def duration_s(self) -> float:
        return self.n_records * self.record_duration_s


def read_edf_header(path: Path) -> EdfHeader:
    """Parse an EDF header without loading signal data.

    Layout: a fixed 256-byte header, then per-signal blocks. Every field is
    ASCII text, space-padded. See https://www.edfplus.info/specs/edf.html
    """
    with open(path, "rb") as fh:
        fixed = fh.read(256)
        if len(fixed) < 256:
            raise ValueError(f"{path} is too short to be an EDF file")

        n_records = int(fixed[236:244].decode("ascii").strip())
        record_duration = float(fixed[244:252].decode("ascii").strip())
        n_signals = int(fixed[252:256].decode("ascii").strip())

        # Per-signal blocks preceding samples-per-record, in bytes each:
        # label 16, transducer 80, dimension 8, phys min 8, phys max 8,
        # digital min 8, digital max 8, prefiltering 80  ->  216 per signal.
        fh.seek(256 + n_signals * 216)
        samples_per_record = int(fh.read(8).decode("ascii").strip())

    return EdfHeader(
        n_channels=n_signals,
        n_records=n_records,
        record_duration_s=record_duration,
        sfreq_hz=samples_per_record / record_duration,
    )