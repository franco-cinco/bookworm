# coding: utf-8

import wx
import wx.lib.mixins.listctrl as listmix
import wx.lib.sized_controls as sc
from itertools import chain
from bookworm.logger import logger


log = logger.getChild(__name__)


def make_sized_static_box(parent, title):
    stbx = sc.SizedStaticBox(parent, -1, title)
    stbx.SetSizerProp("expand", True)
    stbx.Sizer.AddSpacer(25)
    return stbx


class EnhancedSpinCtrl(wx.SpinCtrl):
    """Select the content of the ctrl when
    focused to make editing more easier.
    Inspired by a simular code in NVDA's gui package.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus, self)

    def onFocus(self, event):
        event.Skip()
        length = len(str(self.GetValue()))
        self.SetSelection(0, length)


class PageRangeControl(sc.SizedPanel):
    def __init__(self, parent, document):
        parent = parent
        self.doc = document
        num_pages = len(self.doc)

        # Translators: the title of a group of controls in the search dialog
        rangeBox = make_sized_static_box(parent, _("Search Range"))
        # Translators: the label of a radio button in the search dialog
        self.hasPage = wx.RadioButton(rangeBox, -1, _("Page Range"), style=wx.RB_GROUP)
        fromToPagePanel = make_sized_static_box(rangeBox, "")
        fromToPagePanel.SetSizerProps(expand=True)
        fromToPagePanel.SetSizerType("horizontal")
        # Translators: the label of an edit field in the search dialog
        # to enter the page from which the search will start
        fpage_label = wx.StaticText(fromToPagePanel, -1, _("From:"))
        self.fromPage = EnhancedSpinCtrl(
            fromToPagePanel, -1, min=1, max=num_pages, value="1"
        )
        # Translators: the label of an edit field in the search dialog
        # to enter the page number at which the search will stop
        tpage_label = wx.StaticText(fromToPagePanel, -1, _("To:"))
        self.toPage = EnhancedSpinCtrl(
            fromToPagePanel, -1, min=1, max=num_pages, value=str(num_pages)
        )
        # Translators: the label of a radio button in the search dialog
        self.hasSection = wx.RadioButton(rangeBox, -1, _("Specific section"))
        # Translators: the label of a combobox in the search dialog
        # to choose the section to which the search will be confined
        sec_label = wx.StaticText(rangeBox, -1, _("Select section:"))
        self.sectionChoice = wx.Choice(
            rangeBox, -1, choices=[sect.title for sect in self.doc.toc_tree]
        )
        self.page_controls = (fpage_label, tpage_label, self.fromPage, self.toPage)
        self.sect_controls = (sec_label, self.sectionChoice)
        for ctrl in chain(self.page_controls, self.sect_controls):
            ctrl.Enable(False)
        for radio in (self.hasPage, self.hasSection):
            radio.SetValue(0)
            parent.Bind(wx.EVT_RADIOBUTTON, self.onRangeTypeChange, radio)

    def onRangeTypeChange(self, event):
        radio = event.GetEventObject()
        if radio == self.hasPage:
            controls = self.page_controls
        else:
            controls = self.sect_controls
        for ctrl in chain(self.page_controls, self.sect_controls):
            ctrl.Enable(ctrl in controls)

    def get_range(self):
        if self.hasSection.GetValue():
            selected_section = self.sectionChoice.GetSelection()
            if selected_section != wx.NOT_FOUND:
                pager = self.doc.toc_tree[selected_section].pager
                from_page = pager.first
                to_page = pager.last
        else:
            from_page = self.fromPage.GetValue() - 1
            to_page = self.toPage.GetValue() - 1
        return from_page, to_page


class DialogListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    def __init__(
        self,
        parent,
        ID,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.BORDER_SUNKEN
        | wx.LC_SINGLE_SEL
        | wx.LC_REPORT
        | wx.LC_EDIT_LABELS
        | wx.LC_VRULES,
    ):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)


class Dialog(wx.Dialog):
    """Base dialog for `Bookworm` GUI dialogs."""

    def __init__(self, parent, title, size=(450, 450), style=wx.DEFAULT_DIALOG_STYLE):
        super().__init__(parent, title=title, style=style)
        self.parent = parent

        panel = wx.Panel(self, -1, size=size)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.addControls(sizer, panel)
        line = wx.StaticLine(panel, -1, size=(20, -1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP, 10)
        buttonsSizer = self.getButtons(panel)
        if buttonsSizer:
            sizer.Add(buttonsSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        panel.Layout()
        sizer.Fit(panel)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 2, wx.EXPAND | wx.ALL, 15)
        self.SetSizer(sizer)
        self.Fit()
        self.Center()

    def addControls(self, sizer):
        raise NotImplementedError

    def getButtons(self, parent):
        btnsizer = wx.StdDialogButtonSizer()
        # Translators: the lable of the OK button in a dialog
        okBtn = wx.Button(parent, wx.ID_OK, _("OK"))
        okBtn.SetDefault()
        # Translators: the lable of the cancel button in a dialog
        cancelBtn = wx.Button(parent, wx.ID_CANCEL, _("Cancel"))
        for btn in (okBtn, cancelBtn):
            btnsizer.AddButton(btn)
        btnsizer.Realize()
        return btnsizer


class SimpleDialog(sc.SizedDialog):
    """Basic dialog for simple  GUI forms."""

    def __init__(self, parent, title, style=wx.DEFAULT_DIALOG_STYLE):
        super().__init__(parent, title=title, style=style)
        self.parent = parent

        panel = self.GetContentsPane()
        self.addControls(panel)
        buttonsSizer = self.getButtons(panel)
        if buttonsSizer:
            self.SetButtonSizer(buttonsSizer)

        self.Fit()
        self.SetMinSize(self.GetSize())
        self.Center(wx.BOTH)

    def SetButtonSizer(self, sizer):
        bottomSizer = wx.BoxSizer(wx.VERTICAL)
        line = wx.StaticLine(self, -1, size=(20, -1), style=wx.LI_HORIZONTAL)
        bottomSizer.Add(line, 0, wx.TOP | wx.EXPAND, 15)
        bottomSizer.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)
        super().SetButtonSizer(bottomSizer)

    def addControls(self, parent):
        raise NotImplementedError

    def getButtons(self, parent):
        btnsizer = wx.StdDialogButtonSizer()
        # Translators: the lable of the OK button in a dialog
        okBtn = wx.Button(self, wx.ID_OK, _("OK"))
        okBtn.SetDefault()
        # Translators: the lable of the cancel button in a dialog
        cancelBtn = wx.Button(self, wx.ID_CANCEL, _("Cancel"))
        for btn in (okBtn, cancelBtn):
            btnsizer.AddButton(btn)
        btnsizer.Realize()
        return btnsizer


class SnakDialog(SimpleDialog):
    """A Toast style notification  dialog for showing a simple message without a title."""

    def __init__(self, message, *args, dismiss_callback=None, **kwargs):
        self.message = message
        self.dismiss_callback = dismiss_callback
        super().__init__(*args, title="", style=0, **kwargs)

    def addControls(self, parent):
        self.staticMessage = wx.StaticText(parent, -1, self.message)
        self.staticMessage.SetCanFocus(True)
        self.staticMessage.SetFocusFromKbd()
        self.Bind(wx.EVT_CLOSE, self.onClose, self)
        self.staticMessage.Bind(wx.EVT_KEY_UP, self.onKeyUp, self.staticMessage)
        self.CenterOnParent()

    def onClose(self, event):
        if event.CanVeto():
            if self.dismiss_callback is not None:
                should_close = self.dismiss_callback()
                if should_close:
                    self.Hide()
                    return
            event.Veto()
        else:
            self.Destroy()

    def onKeyUp(self, event):
        event.Skip()
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()

    def getButtons(self, parent):
        return
