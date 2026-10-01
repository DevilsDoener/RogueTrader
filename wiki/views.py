from collections import Counter
from functools import lru_cache, wraps

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView, View

from .content import get_repository
from .manifest import BANDS
from .search import MIN_QUERY_LENGTH, is_searchable
from .suggest import suggest

#: Hits shown on the results page; the rest are reachable via the chapter facets.
SEARCH_RESULTS_LIMIT = 50


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


def _library_card(chapter):
    """One overview card: the chapter plus the text the live filter matches.

    The filter string is built here (not in the template) so autoescape stays
    in charge of quotes and angle brackets in section titles. It covers the
    chapter title and its level-1 and level-2 sections, casefolded; the
    template nests each level-1 section's children under it, so a level-2
    match can be shown and marked too.
    """
    sections = chapter.navigable_sections
    words = [chapter.short_title, chapter.title]
    for section in sections:
        words.append(section.title)
        words.extend(child.title for child in section.children)
    return {
        "chapter": chapter,
        "sections": sections,
        "filter_text": " ".join(words).casefold(),
    }


@lru_cache(maxsize=1)
def _library_bands(repository):
    """The manifest's bands in order, each with its chapters' cards.

    Every numbered chapter (I-XV, including the four files of XIV) shares the
    one "Chapters" grid. The repository is immutable, so the result is built
    once per repository; templates only read it.
    """
    cards = {name: [] for name in BANDS}
    for chapter in repository.chapters():
        cards[chapter.band].append(_library_card(chapter))
    return [{"name": name, "cards": cards[name]} for name in BANDS if cards[name]]


@gzip_unless_query
class WikiIndexView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = get_repository()
        context["bands"] = _library_bands(repository)
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
        repository = get_repository()
        query = self.request.GET.get("q", "")
        all_results = repository.search(query, limit=None) if query else ()

        # One facet per chapter with at least one hit, in book order.
        counts = Counter(result.chapter_slug for result in all_results)
        facets = [
            {"chapter": chapter, "count": counts[chapter.slug]}
            for chapter in repository.chapters()
            if counts[chapter.slug]
        ]
        # An unknown or hit-less ?kapitel= is ignored rather than producing an
        # empty page the reader cannot explain.
        requested = self.request.GET.get("kapitel", "")
        active_chapter = next(
            (f["chapter"] for f in facets if f["chapter"].slug == requested), None
        )
        filtered = (
            [r for r in all_results if r.chapter_slug == active_chapter.slug]
            if active_chapter
            else list(all_results)
        )
        shown = filtered[:SEARCH_RESULTS_LIMIT]

        context["query"] = query
        # (result, chapter) pairs: templates cannot index a dict by a variable,
        # and each card shows its chapter's numeral and short title.
        context["hits"] = [
            (result, repository.get_chapter(result.chapter_slug)) for result in shown
        ]
        context["total_count"] = len(filtered)
        context["all_count"] = len(all_results)
        context["facets"] = facets
        context["active_chapter"] = active_chapter
        context["results_capped"] = len(filtered) > SEARCH_RESULTS_LIMIT
        context["search_results_limit"] = SEARCH_RESULTS_LIMIT
        context["quick_links"] = repository.quick_links()
        # Distinguishes "too short to search" from "searched, found nothing",
        # which the template could not tell apart from an empty result tuple.
        context["query_too_short"] = bool(query) and not is_searchable(query)
        context["min_query_length"] = MIN_QUERY_LENGTH
        return context


class WikiSuggestView(LoginRequiredMixin, View):
    """JSON suggestions for the Auspex palette; deliberately not gzip-wrapped."""

    def get(self, request):
        response = JsonResponse(suggest(get_repository(), request.GET.get("q", "")))
        response["Cache-Control"] = "private, max-age=60"
        return response
