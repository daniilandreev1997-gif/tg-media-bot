from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.services.downloader import YtDlpDownloader
from app.services.queue import DownloadQueue
from app.storage.repositories import CredentialStore, JobRepository, SettingsRepository, UserRepository


@dataclass(slots=True)
class AppContext:
    settings: Settings
    users: UserRepository
    jobs: JobRepository
    credentials: CredentialStore
    settings_repo: SettingsRepository
    downloader: YtDlpDownloader
    queue: DownloadQueue
