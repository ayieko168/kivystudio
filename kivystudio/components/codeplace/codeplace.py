
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition, ScreenManagerException
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ToggleButtonBehavior, FocusBehavior
from kivy.uix.boxlayout import BoxLayout

from kivy import properties as prop
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.extras.highlight import KivyLexer


from kivystudio.widgets.codeinput import FullCodeInput
from kivystudio.widgets.filemanager import filemanager
from kivystudio.components.emulator_area import get_emulator_area
from kivystudio.tools import quicktools, load_kv
from kivystudio.tools.logger import Logger

from .tabs.welcometab import WelcomeTab
from .tabs.codetab import TabToggleButton
from .tabs.errortab import FileErrorTab

from pygments import lexers
import os

# file_formats = ['.py', '.kv', '.spec', '.txt']

def get_tab_from_group(filename):
    all_tabs = ToggleButtonBehavior.get_widgets('__tabed_btn__')
    if not all_tabs: return
    for tab in all_tabs:
        if tab.filename == filename:
            return tab


def get_lexer_for_file(filename):
    ext = os.path.splitext(filename)[1]
    try:
        lexer = lexers.get_lexer_for_filename(filename)
    except lexers.ClassNotFound:
        if ext == '.kv':
            lexer = KivyLexer()
        else:
            lexer = lexers.TextLexer()
    # print('found {} for {}'.format(lexer, filename))
    return lexer


class CodeScreenManager(ScreenManager):

    def __init__(self, **kwargs):
        super(CodeScreenManager, self).__init__(**kwargs)
        self.transition = NoTransition()

    def add_widget(self, widget, name, tab_type='code'):
        if tab_type=='code':
            Clock.schedule_once(lambda dt: self.open_file(widget),1)     # open the file

        try:
            widget.code_input.lexer = get_lexer_for_file(widget.filename)
        except:
            pass

        screen = CodeScreen(name=name)
        screen.add_widget(widget,tab_type=tab_type)
        super(CodeScreenManager, self).add_widget(screen)

    def open_file(self, code_input):
        if os.path.exists(code_input.filename):
            with open(code_input.filename, 'r') as f:
                code_input.code_input.focus = False
                code_input.code_input.text = f.read()

    def save_current_tab(self):
        self.get_screen(self.current).save_file()

    def save_all_tabs(self):
        for name in self.screen_names:
            self.get_screen(name).save_file()

    def get_children_with_filename(self, filename):
        try:
            child = list(filter(lambda child: child.name==filename, self.screens))[0]
            return child
        except IndexError:
            raise Exception('code manager as no child with such filename {}'.format(filename))


class CodeScreen(Screen):
    
    code_field = prop.ObjectProperty(None)

    def on_pre_enter(self):
        if self.code_field:
            self.code_field.code_input.focus = True
            Window.bind(on_key_down=self.keyboard_down)

        tab = get_tab_from_group(self.name)
        if tab:
            Clock.schedule_once(lambda dt: setattr(tab, 'state', 'down'))


    def on_pre_leave(self):
        if self.code_field:
            Window.unbind(on_key_down=self.keyboard_down)

    def on_enter(self):
        if self.code_field:
            self.code_field.code_input.focus = True

    def save_file(self, new_file=False, auto_save=False):
        if self.code_field.tab_type=='code':
            if not self.code_field.saved or new_file:
                with open(self.name, 'w') as fn:
                    fn.write(self.code_field.code_input.text)
    
            self.code_field.saved = True
        if new_file:
            self.code_field.code_input.lexer = get_lexer_for_file(self.name)
                
        if self.code_field.tab_type=='new_file' and not auto_save:
            filemanager.save_file(path='/root', on_selection=self.save_new_file)


    def save_new_file(self, paths):
        if paths:
            path=paths[0]
            self.code_field.tab.filename=path
            self.code_field.tab.text = os.path.split(path)[1]
            self.code_field.tab_type='code'
            self.name=path
            self.save_file(new_file=True)

    def add_widget(self, widget, tab_type='code'):
        super(CodeScreen, self).add_widget(widget)
        if tab_type=='code' or tab_type=='new_file':
            self.code_field = widget
            self.code_field.tab_type=tab_type
            self.code_field.bind(saved=self.saving_file)

    def saving_file(self, ins, saved):
        tab = get_tab_from_group(self.name)
        tab.saved = saved       

    def keyboard_down(self, window, *args):
        # print(args)
        if args[0] == 115 and 'ctrl' in args[3]:  # save file Ctrl+S
            self.save_file()
            return False

        if args[0] == 101 and 'ctrl' in args[3]:  # select file for emulation file Ctrl+E
            if os.path.exists(self.name):
                get_emulator_area().emulation_file=self.name
                Logger.info("Emulator: File '{}' selected".format(self.name))
            else:
                Logger.info("Emulator: invalid file selected".format(self.name))


class CodePlace(BoxLayout):
    
    code_manager = prop.ObjectProperty(None)

    tab_manager = prop.ObjectProperty(None)

    new_empty_tab = prop.NumericProperty(0)
    '''count of empty tabs that has been opened
    '''

    def __init__(self, **kwargs):
        super(CodePlace, self).__init__(**kwargs)
        self.code_manager = CodeScreenManager()
        self.add_widget(self.code_manager)

        Window.bind(on_key_down=self.keyboard_down)
        Window.bind(on_dropfile=self.file_droped)

    def file_droped(self, window, filename, *args):
        if self.collide_point(*window.mouse_pos):
            print('File droped on code input {} '.format(filename))
            if filename:
                self.add_code_tab(filename=filename.decode('utf-8'))

    def add_widget(self, widget, tab_type=''):
        if len(self.children) > 1:
            if tab_type =='code' or tab_type =='new_file' or tab_type=='unsupported':
                tab = TabToggleButton(text=os.path.split(widget.filename)[1],
                                    filename=widget.filename)
                widget.tab = tab
                widget.tab_type = tab_type
                self.code_manager.add_widget(widget, widget.filename, tab_type=tab_type)

            elif tab_type=='welcome':
                self.code_manager.add_widget(widget, 'kivystudiowelcome', tab_type=tab_type)
                tab = TabToggleButton(text='Welcome',filename='kivystudiowelcome')

            tab.bind(state=self.change_screen)
            self.tab_manager.add_widget(tab)
            Clock.schedule_once(lambda dt: setattr(tab, 'state', 'down'))

        else:
            super(CodePlace, self).add_widget(widget)

    def change_screen(self, tab, state):
        if state == 'down':
            self.code_manager.current = tab.filename
            checked_list = list(filter(lambda child: child != tab, ToggleButtonBehavior.get_widgets(tab.group)))
            for child in checked_list:
                if child != tab:
                    child.state='normal'

    def keyboard_down(self, window, *args):

        if args[0] == 9 and args[3] == ['ctrl']:   # switching screen with ctrl tab
            self.code_manager.current = self.code_manager.next()
            return True

        if args[0] == 119 and args[3] == ['ctrl']:   # close tab
            try:
                name = self.code_manager.get_screen(self.code_manager.current).name
                tab = get_tab_from_group(name)
                self.remove_code_tab(tab)
            except ScreenManagerException:
                pass

    def remove_code_tab(self, tab):
        self.tab_manager.remove_widget(tab)
        codeinput=self.code_manager.get_children_with_filename(tab.filename)
        self.code_manager.remove_widget(codeinput)

        if tab.filename.startswith('Untitled-') and not os.path.exists(tab.filename):
            self.new_empty_tab -= 1

    def add_code_tab(self, filename='', tab_type='code'):
        if filename and os.path.exists(filename):
            if not quicktools.is_binary(filename):
                widget=FullCodeInput(filename=filename)
            else:
                widget=FileErrorTab(filename=filename)
                tab_type='unsupported'
            try:
                self.code_manager.get_screen(filename)
                self.code_manager.current=filename
            except ScreenManagerException:   # then it is not added
                self.add_widget(widget, tab_type=tab_type)

        elif tab_type=='new_file':   # a new tab
            self.new_empty_tab += 1
            while True:
                try:
                    self.code_manager.get_screen(filename)
                    self.code_manager.current=filename
                except ScreenManagerException:   # then it is not added
                    filename = 'Untitled-{}'.format(self.new_empty_tab)
                    self.add_widget(FullCodeInput(filename=filename), tab_type=tab_type)
                    return
                self.new_empty_tab += 1

        elif tab_type == 'welcome':
            try:
                self.code_manager.get_screen('kivystudiowelcome')
                self.code_manager.current=filename
            except ScreenManagerException:   # then it is not added
                self.add_widget(WelcomeTab(), tab_type=tab_type)



class CodeTabsContainer(ScrollView):
    '''horizontal scrollview where the small tab 
        buttons lay'''

    def on_touch_down(self, touch):
        FocusBehavior.ignored_touch.append(touch)
        return super(CodeTabsContainer, self).on_touch_down(touch)

load_kv(__file__, 'code.kv')
