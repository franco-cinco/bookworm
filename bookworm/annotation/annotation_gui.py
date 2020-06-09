# coding: utf-8

import wx
from collections.abc import Container
from dataclasses import dataclass
from enum import IntEnum
from bookworm import config
from bookworm import speech
from bookworm.utils import gui_thread_safe
from bookworm.gui.settings import SettingsPanel
from bookworm.logger import logger
from .annotator import Bookmarker, NoteTaker, Quoter
from .annotation_dialogs import BookmarksViewer, ExportNotesDialog


log = logger.getChild(__name__)


class AnnotationSettingsPanel(SettingsPanel):
    config_section = "annotation"

    def addControls(self):
        # Translators: the title of a group of controls in the
        UIBox = self.make_static_box(_("Annotations"))
        wx.CheckBox(
            UIBox,
            -1,
            # Translators: the label of a checkbox
            _("Use visual styles to indicate annotations"),
            name="annotation.use_visuals",
        )
        wx.CheckBox(
            UIBox,
            -1,
            # Translators: the label of a checkbox
            _("Use sounds to indicate the presence of comments"),
            name="annotation.play_sound_for_comments",
        )


class AnnotationsMenuIds(IntEnum):
    addBookmark = 241
    addNamedBookmark = 242
    addNote = 243
    quoteSelection = 244
    viewBookmarks = 245
    viewNotes = 246
    viewQuotes = 247
    ExportAnnotations = 248


ANNOTATIONS_KEYBOARD_SHORTCUTS = {
    AnnotationsMenuIds.addBookmark: "Ctrl-B",
    AnnotationsMenuIds.addNamedBookmark: "Ctrl-Shift-B",
    AnnotationsMenuIds.addNote: "Ctrl-M",
    AnnotationsMenuIds.quoteSelection: "Ctrl-H",
}


@dataclass
class SelectionRange(Container):
    """Represents a text range in an edit control."""

    start: int
    end: int

    def __contains__(self, x):
        return self.start <= x <= self.end


class AnnotationMenu(wx.Menu):
    """Annotation menu."""

    def __init__(self, service, menubar):
        super().__init__()
        self.service = service
        self.view = service.view
        self.reader = service.reader
        self.menubar = menubar

        # Add menu items
        self.Append(
            AnnotationsMenuIds.addBookmark,
            # Translators: the label of an item in the application menubar
            _("Add &Bookmark\tCtrl-B"),
            # Translators: the help text of an item in the application menubar
            _("Add a bookmark at the current position"),
        )
        self.Append(
            AnnotationsMenuIds.addNamedBookmark,
            # Translators: the label of an item in the application menubar
            _("Add &Named Bookmark...\tCtrl-Shift-B"),
            # Translators: the help text of an item in the application menubar
            _("Add a named bookmark at the current position"),
        )
        self.Append(
            AnnotationsMenuIds.addNote,
            # Translators: the label of an item in the application menubar
            _("Add Co&mment...\tCtrl-M"),
            # Translators: the help text of an item in the application menubar
            _("Add a comment at the current position"),
        )
        self.Append(
            AnnotationsMenuIds.quoteSelection,
            # Translators: the label of an item in the application menubar
            _("&Highlight Selection\tCtrl-H"),
            # Translators: the help text of an item in the application menubar
            _("Highlight selected text and save it."),
        )
        self.Append(
            AnnotationsMenuIds.viewBookmarks,
            # Translators: the label of an item in the application menubar
            _("Saved &Bookmarks..."),
            # Translators: the help text of an item in the application menubar
            _("View added bookmarks"),
        )
        self.Append(
            AnnotationsMenuIds.viewNotes,
            # Translators: the label of an item in the application menubar
            _("Saved Co&mments..."),
            # Translators: the help text of an item in the application menubar
            _("View, edit, and remove comments."),
        )
        self.Append(
            AnnotationsMenuIds.viewQuotes,
            # Translators: the label of an item in the application menubar
            _("Saved &Highlights..."),
            # Translators: the help text of an item in the application menubar
            _("View saved highlights."),
        )
        # Export submenu
        exportMenu = wx.Menu()
        exportCommentsId = wx.NewIdRef()
        exportQuotesId = wx.NewIdRef()
        exportMenu.Append(
            exportCommentsId,
            # Translators: the label of an item in the application menubar
            _("Export Co&mments") + "...",
            # Translators: the help text of an item in the application menubar
            _("Export comments to a file."),
        )
        exportMenu.Append(
            exportQuotesId,
            # Translators: the label of an item in the application menubar
            _("Export &Highlights") + "...",
            # Translators: the help text of an item in the application menubar
            _("Export quotes to a file."),
        )
        # Translators: the label of an item in the application menubar
        self.Append(wx.ID_ANY, _("&Export"), exportMenu)

        # Translators: the label of an item in the application menubar
        self.menubar.Insert(2, self, _("&Annotations"))

        # EventHandlers
        self.view.Bind(
            wx.EVT_MENU, self.onAddBookmark, id=AnnotationsMenuIds.addBookmark
        )
        self.view.Bind(
            wx.EVT_MENU, self.onAddNamedBookmark, id=AnnotationsMenuIds.addNamedBookmark
        )
        self.view.Bind(wx.EVT_MENU, self.onAddNote, id=AnnotationsMenuIds.addNote)
        self.view.Bind(
            wx.EVT_MENU, self.onQuoteSelection, id=AnnotationsMenuIds.quoteSelection
        )
        self.view.Bind(
            wx.EVT_MENU, self.onViewBookmarks, id=AnnotationsMenuIds.viewBookmarks
        )
        self.view.Bind(wx.EVT_MENU, self.onViewNotes, id=AnnotationsMenuIds.viewNotes)
        self.view.Bind(wx.EVT_MENU, self.onViewQuotes, id=AnnotationsMenuIds.viewQuotes)
        self.view.Bind(wx.EVT_MENU, self.onExportComments, id=exportCommentsId)
        self.view.Bind(wx.EVT_MENU, self.onExportQuotes, id=exportQuotesId)

    def _add_bookmark(self, name=""):
        bookmarker = Bookmarker(self.reader)
        insertionPoint = self.view.contentTextCtrl.GetInsertionPoint()
        __, __, current_lino = self.view.contentTextCtrl.PositionToXY(insertionPoint)
        count = 0
        for bkm in bookmarker.get_for_page(self.reader.current_page):
            __, __, lino = self.view.contentTextCtrl.PositionToXY(bkm.position)
            if lino == current_lino:
                count += 1
                bookmarker.delete(bkm.id)
                self.service.style_bookmark(self.view, bkm.position, enable=False)
        if count and not name:
            return speech.announce("Bookmark removed.")
        Bookmarker(self.reader).create(title=name, position=insertionPoint)
        # Translators: spoken message
        speech.announce(_("Bookmark Added"))
        self.service.style_bookmark(self.view, insertionPoint)

    def onAddBookmark(self, event):
        self._add_bookmark()

    def onAddNamedBookmark(self, event):
        bookmark_name = self.get_text_from_user(
            # Translators: title of a dialog
            _("Add Named Bookmark"),
            # Translators: label of a text entry
            _("Bookmark name:"),
        )
        if bookmark_name:
            self._add_bookmark(bookmark_name)

    def onAddNote(self, event):
        _with_tags = wx.GetKeyState(wx.WXK_SHIFT)
        insertionPoint = self.view.contentTextCtrl.GetInsertionPoint()
        comment_text = self.get_text_from_user(
            # Translators: the title of a dialog to add a comment
            _("New Comment"),
            # Translators: the label of an edit field to enter a comment
            _("Comment:"),
            style=wx.OK | wx.CANCEL | wx.TE_MULTILINE | wx.CENTER,
        )
        if not comment_text:
            return
        note = NoteTaker(self.reader).create(
            title="", content=comment_text, position=insertionPoint
        )
        self.service.style_comment(self.view, insertionPoint)
        if _with_tags:
            # add tags
            tags_text = self.get_text_from_user(
                # Translators: title of a dialog
                _("Tag Comment"),
                # Translators: label of a text entry
                _("Tags:"),
            )
            if tags_text:
                for tag in tags_text.split():
                    note.tags.append(tag.strip())
                NoteTaker.model.session.commit()

    def onQuoteSelection(self, event):
        _with_tags = wx.GetKeyState(wx.WXK_SHIFT)
        quoter = Quoter(self.reader)
        selected_text = self.view.contentTextCtrl.GetStringSelection()
        if not selected_text:
            return speech.announce(_("No selection"))
        x, y = self.view.contentTextCtrl.GetSelection()
        for q in quoter.get_for_page():
            q_range = SelectionRange(q.start_pos, q.end_pos)
            if (q_range.start == x) and (q_range.end == y):
                quoter.delete(q.id)
                self.service.style_highlight(self.view, x, y, enable=False)
                # Translators: spoken message
                return speech.announce(_("Highlight removed"))
            elif (q.start_pos < x) and (q.end_pos > y):
                # Translators: spoken message
                speech.announce(_("Already highlighted"))
                return wx.Bell()
            if (x in q_range) or (y in q_range):
                if x not in q_range:
                    q.start_pos = x
                    q.session.commit()
                    self.service.style_highlight(self.view, x, q_range.end)
                    return speech.announce(_("Highlight extended"))
                elif y not in q_range:
                    q.end_pos = y
                    q.session.commit()
                    self.service.style_highlight(self.view, q_range.start, y)
                    # Translators: spoken message
                    return speech.announce(_("Highlight extended"))
        quote = quoter.create(title="", content=selected_text, start_pos=x, end_pos=y)
        # Translators: spoken message
        speech.announce("Selection highlighted")
        self.service.style_highlight(self.view, x, y)
        if _with_tags:
            # add tags
            tags_text = self.get_text_from_user(
                # Translators: title of a dialog
                _("Tag Highlight"),
                # Translators: label of a text entry
                _("Tags:"),
            )
            if tags_text:
                for tag in tags_text.split():
                    quote.tags.append(tag.strip())
                Quoter.model.session.commit()

    def onViewBookmarks(self, event):
        dlg = BookmarksViewer(
            parent=self.view,
            reader=self.reader,
            annotator=Bookmarker,
            # Translators: the title of a dialog to view bookmarks
            title=_("Bookmarks | {book}").format(book=self.reader.current_book.title),
        )
        with dlg:
            dlg.ShowModal()

    def onViewNotes(self, event):
        ...

    def onViewQuotes(self, event):
        ...

    def onExportComments(self, event):
        ...

    def onExportQuotes(self, event):
        ...

    def get_text_from_user(
        self, title, label, style=wx.OK | wx.CANCEL | wx.CENTER, value=""
    ):
        dlg = wx.TextEntryDialog(self.view, label, title, style=style)
        if dlg.ShowModal() == wx.ID_OK:
            value = dlg.GetValue().strip()
            return value or wx.Bell()
