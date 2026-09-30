"""Template context shared by every wiki page.

The primary nav in ``templates/base.html`` lists the chapters as a sub-tree
under "Wiki" while the reader is anywhere in the wiki (index, chapter,
search). Outside the wiki the nav stays short, so nothing is computed there.
"""
from .content import get_repository_or_none


def wiki_navigation(request):
    match = getattr(request, "resolver_match", None)
    if match is None or match.app_name != "wiki":
        return {"wiki_nav_chapters": ()}
    # No repository (e.g. a management command rendering a template): the nav
    # simply has no chapter tree then.
    repository = get_repository_or_none()
    return {"wiki_nav_chapters": repository.chapters() if repository is not None else ()}
