from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView

from .content import get_repository
from .search import MIN_QUERY_LENGTH

PLACEHOLDER_TEXT = "Dieses Kapitel ist noch nicht ausgearbeitet."


# Chapters render up to ~150 KB of HTML, which compresses to about 21 KB.
# Scoped to the two views that reflect no user input rather than applied
# globally: the search view echoes `q`, and keeping compression away from
# responses that mix a secret with attacker-influenced content keeps the BREACH
# argument trivial instead of relying on Django's CSRF masking alone.
gzip_chapter_html = method_decorator(gzip_page, name="dispatch")


@gzip_chapter_html
class WikiIndexView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = get_repository()
        context["chapters"] = repository.chapters()
        context["parts"] = repository.parts()
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
        query = self.request.GET.get("q", "")
        context["query"] = query
        context["results"] = get_repository().search(query) if query else ()
        # Distinguishes "too short to search" from "searched, found nothing",
        # which the template could not tell apart from an empty result tuple.
        context["query_too_short"] = bool(query) and (
            len(query.replace(" ", "")) < MIN_QUERY_LENGTH
        )
        context["min_query_length"] = MIN_QUERY_LENGTH
        return context
