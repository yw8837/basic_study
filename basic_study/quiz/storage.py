import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


class BaseStorage(ABC):
    @abstractmethod
    def save_session(self, result: dict) -> None: ...

    @abstractmethod
    def get_history(self) -> list[dict]: ...

    @abstractmethod
    def save_wrong(self, question_id: str, question: dict) -> None: ...

    @abstractmethod
    def get_wrong_notes(self) -> list[dict]: ...


class LocalJSONStorage(BaseStorage):
    def __init__(self):
        base = Path.home() / ".basic_study"
        try:
            base.mkdir(exist_ok=True)
        except OSError:
            base = Path("/tmp/.basic_study")
            base.mkdir(exist_ok=True)
        self._progress_path = base / "progress.json"
        self._wrong_path = base / "wrong_notes.json"

    def _read(self, path: Path) -> list:
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, path: Path, data: list) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def save_session(self, result: dict) -> None:
        history = self._read(self._progress_path)
        history.append({**result, "timestamp": datetime.now().isoformat()})
        self._write(self._progress_path, history)

    def get_history(self) -> list[dict]:
        return self._read(self._progress_path)

    def save_wrong(self, question_id: str, question: dict) -> None:
        notes = self._read(self._wrong_path)
        existing_ids = {n["id"] for n in notes}
        if question_id not in existing_ids:
            notes.append({"id": question_id, "question": question,
                          "added": datetime.now().isoformat()})
            self._write(self._wrong_path, notes)

    def get_wrong_notes(self) -> list[dict]:
        return self._read(self._wrong_path)
