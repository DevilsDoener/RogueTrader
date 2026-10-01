import pytest

from wiki.content import WikiRepository, set_repository_for_tests


@pytest.fixture
def make_repository(tmp_path, settings):
    """Serve ``{file name: text}`` from ``tmp_path`` and load it.

    Text may be ``bytes`` to write a file verbatim (e.g. invalid UTF-8). With
    ``install=True`` the repository also becomes the process-wide one the
    views read; the root conftest's autouse
    ``_restore_wiki_repository`` restores the previous one.
    """

    def make(files, *, install=False):
        for name, text in files.items():
            path = tmp_path / name
            if isinstance(text, bytes):
                path.write_bytes(text)
            else:
                path.write_text(text, encoding="utf-8")
        settings.WIKI_CONTENT_ROOT = tmp_path
        settings.WIKI_CONTENT_ALLOWLIST = list(files)
        repository = WikiRepository.load()
        if install:
            set_repository_for_tests(repository)
        return repository

    return make
