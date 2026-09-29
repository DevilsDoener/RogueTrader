from collections import Counter

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView, View

from .content import get_repository
from .search import MIN_QUERY_LENGTH
from .suggest import suggest

#: Hits shown on the results page; the rest are reachable via the chapter facets.
SEARCH_RESULTS_LIMIT = 50
PLACEHOLDER_TEXT = "Dieses Kapitel ist noch nicht ausgearbeitet."


# Chapters render up to ~150 KB of HTML, which compresses to about 21 KB.
# Scoped to the two views that reflect no user input rather than applied
# globally: the search view echoes `q`, and keeping compression away from
# responses that mix a secret with attacker-influenced content keeps the BREACH
# argument trivial instead of relying on Django's CSRF masking alone. The
# suggest endpoint echoes `q` too, so it stays uncompressed for the same reason.
gzip_chapter_html = method_decorator(gzip_page, name="dispatch")


def _library_card(chapter):
    """One overview card: the chapter plus the text the live filter matches.

    The filter string is built here (not in the template) so autoescape stays
    in charge of quotes and angle brackets in section titles. It covers the
    chapter title and its level-1 and level-2 sections, casefolded.
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


@gzip_chapter_html
class WikiIndexView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = get_repository()
        context["chapters"] = repository.chapters()
        context["parts"] = repository.parts()
        context["library_parts"] = [
            {
                "name": part_name,
                # Only a part collecting several files earns its own heading;
                # a single-chapter part would repeat the chapter title.
                "show_heading": len(part_chapters) > 1,
                "cards": [_library_card(chapter) for chapter in part_chapters],
            }
            for part_name, part_chapters in repository.parts()
        ]
        context["quick_links"] = repository.quick_links()
        return context


@gzip_chapter_html
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
        context["chapters"] = repository.chapters()
        context["previous_chapter"] = previous_chapter
        context["next_chapter"] = next_chapter
        context["toc_max_depth"] = settings.WIKI_TOC_MAX_DEPTH
        context["placeholder_text"] = PLACEHOLDER_TEXT
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
        context["results"] = shown
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
        context["query_too_short"] = bool(query) and (
            len(query.replace(" ", "")) < MIN_QUERY_LENGTH
        )
        context["min_query_length"] = MIN_QUERY_LENGTH
        return context


class WikiSuggestView(LoginRequiredMixin, View):
    """JSON suggestions for the Auspex palette; deliberately not gzip-wrapped."""

    def get(self, request):
        response = JsonResponse(suggest(get_repository(), request.GET.get("q", "")))
        response["Cache-Control"] = "private, max-age=60"
        return response
