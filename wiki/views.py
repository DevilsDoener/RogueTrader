from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views.generic import TemplateView

from .content import get_repository

PLACEHOLDER_TEXT = "Dieses Kapitel ist noch nicht ausgearbeitet."


class WikiIndexView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapters"] = get_repository().chapters()
        return context


class WikiChapterView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/chapter.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = get_repository()
        chapter = repository.get_chapter(kwargs["chapter_slug"])
        if chapter is None:
            raise Http404("Unknown wiki chapter.")
        context["chapter"] = chapter
        context["chapters"] = repository.chapters()
        context["placeholder_text"] = PLACEHOLDER_TEXT
        return context


class WikiSearchView(LoginRequiredMixin, TemplateView):
    template_name = "wiki/search_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        context["query"] = query
        context["results"] = get_repository().search(query) if query else ()
        return context
