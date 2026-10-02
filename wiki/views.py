from functools import wraps

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView, View

from .content import get_repository
from .search_page import build_search_page
from .suggest import suggest


# Chapters render up to ~150 KB of HTML, which compresses to about 21 KB.
# Compression is applied per view, and only to responses that echo no user
# input: keeping it away from responses that mix a secret with
# attacker-influenced content keeps the BREACH argument trivial instead of
# relying on Django's CSRF masking alone. So the search and suggest views are
# never compressed, and the index and chapter views only without `?q=` (a
# chapter opened from a search result echoes it in the topbar field and the
# highlight terms).
def _gzip_unless_query(view_func):
    compressed = gzip_page(view_func)

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if "q" in request.GET:
            return view_func(request, *args, **kwargs)
        return compressed(request, *args, **kwargs)

    return wrapper


gzip_unless_query = method_decorator(_gzip_unless_query, name="dispatch")


@gzip_unless_query
class WikiIndexView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = get_repository()
        context["bands"] = repository.library_bands
        context["quick_links"] = repository.quick_links()
        return context


@gzip_unless_query
class WikiChapterView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/chapter.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = get_repository()
        chapter = repository.get_chapter(kwargs["chapter_slug"])
        if chapter is None:
            raise Http404("Unknown wiki chapter.")
        previous_chapter, next_chapter = repository.neighbours(chapter.slug)
        context["chapter"] = chapter
        context["previous_chapter"] = previous_chapter
        context["next_chapter"] = next_chapter
        context["toc_max_depth"] = settings.WIKI_TOC_MAX_DEPTH
        # Arriving from a search result (?q=): wiki-reader.js marks these words
        # in the article. The chapter list for the nav comes from
        # wiki.context_processors.wiki_navigation.
        context["highlight_terms"] = list(
            repository.highlight_terms(self.request.GET.get("q", ""))
        )
        return context


class WikiSearchView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/search_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            build_search_page(
                get_repository(),
                self.request.GET.get("q", ""),
                self.request.GET.get("kapitel", ""),
            )
        )
        return context


class WikiSuggestView(LoginRequiredMixin, View):
    """JSON suggestions for the Auspex palette; deliberately not gzip-wrapped."""

    def get(self, request):
        response = JsonResponse(suggest(get_repository(), request.GET.get("q", "")))
        response["Cache-Control"] = "private, max-age=60"
        return response
