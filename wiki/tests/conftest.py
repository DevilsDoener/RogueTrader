import pytest
from django.contrib.auth import get_user_model

from wiki import content
from wiki.content import WikiRepository, set_repository_for_tests


@pytest.fixture
def user_factory(db):
    def create_user(**attributes):
        password = attributes.pop("password", "Valid-Password-42!")
        attributes.setdefault("must_change_password", False)
        username = attributes.pop("username", "user")
        user = get_user_model().objects.create_user(
            username=username,
            password=password,
            **attributes,
        )
        return user

    return create_user


@pytest.fixture(autouse=True)
def _restore_wiki_repository():
    """Undo any ``set_repository_for_tests`` so no test leaks its corpus."""
    saved = content._repository
    yield
    content._repository = saved


@pytest.fixture
def make_repository(tmp_path, settings):
    """Serve ``{file name: text}`` from ``tmp_path`` and load it.

    Text may be ``bytes`` to write a file verbatim (e.g. invalid UTF-8). With
    ``install=True`` the repository also becomes the process-wide one the
    views read; the autouse fixture above restores the previous one.
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
