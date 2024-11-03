from ETS2LA.Plugin.attributes import Global, Plugins, PluginDescription, State
from ETS2LA.Plugin.settings import Settings
from ETS2LA.Plugin.author import Author

from ETS2LA.utils.logging import SetupProcessLogging
from multiprocessing import JoinableQueue
from types import SimpleNamespace
from typing import Literal
import threading
import importlib
import logging
import json
import time
import sys
import os

class ETS2LAPlugin(object):
    """
    This is the main plugin object, you will see a list of attributes below.
    
    :param int fps_cap: The maximum frames per second the plugin will run at.
    :param Description description: The description of the plugin.
    :param Author author: The author of the plugin.
    :param Global globals: The global settings and tags.
    :param Settings settings: The settings of the plugin.
    :param Plugins plugins: Interactions with other plugins.
    """
    path: str

    fps_cap: int = 30
    
    description: PluginDescription = PluginDescription()
    author: Author
    settings_menu: None
    
    return_queue: JoinableQueue
    plugins_queue: JoinableQueue
    plugins_return_queue: JoinableQueue
    settings_menu_queue: JoinableQueue
    settings_menu_return_queue: JoinableQueue
    frontend_queue: JoinableQueue
    frontend_return_queue: JoinableQueue
    immediate_queue: JoinableQueue
    immediate_return_queue: JoinableQueue
    state_queue: JoinableQueue
    performance_queue: JoinableQueue
    performance_return_queue: JoinableQueue
    
    performance: list[tuple[float, float]] = []
    
    state: State
    """
    The state of the plugin shown in the frontend.
    
    Example:
    ```python
    while HeavyOperation():
        percentage = 0.66
        self.state.text = f"Loading... ({round(percentage * 100)}%)"
        self.state.progress = percentage
    
    self.state.reset()
    # or
    self.state.text = ""
    self.state.progress = -1
    ```
    """
    
    globals: Global
    """
    Global class for the plugin to access global settings and
    
    :param GlobalSettings settings: Access to the global settings.
    :param Tags tags: Access to the global tags.
    """
    settings: Settings
    """
    Access the local plugins settings file.
    
    Example:
    ```python
    # Get a setting (doesn't read / write)
    value = self.settings.setting_name
    # Set a setting (does write, don't use each frame)
    self.settings.setting_name = value
    ```
    """
    plugins: Plugins
    """
    Access all the other running plugins' information.
    
    Example:
    ```python
    # Get the plugin return data
    data = self.plugins.plugin_name
    ```
    """
    modules: SimpleNamespace
    """
    Access to all running modules that were defined in the description object.
    
    Example:
    ```python
    
    ```
    """
    
    def ensure_settings_file(self) -> None:
        path = self.path
        if not os.path.exists(f"{path}/settings.json"):
            os.makedirs(path, exist_ok=True)
            with open(f"{path}/settings.json", "w") as file:
                json.dump({}, file)
    
    def ensure_functions(self) -> None:
        if type(self).before != ETS2LAPlugin.before:
            raise TypeError("'before' is a reserved function name")
        if type(self).after != ETS2LAPlugin.after:
            raise TypeError("'after' is a reserved function name")
        if type(self).plugin != ETS2LAPlugin.plugin:
            raise TypeError("'plugin' is a reserved function name, please use 'run' instead")
        if "run" not in dir(type(self)):
            raise TypeError("Your plugin has to have a 'run' function.")
        if "imports" not in dir(type(self)):
            raise TypeError("Your plugin has to have an 'imports' function.")
        if type(self).__name__ != "Plugin":
            raise TypeError("Please make sure the class is named 'Plugin'")
    
    def __new__(cls, path: str, return_queue: JoinableQueue, 
                                plugins_queue: JoinableQueue, plugins_return_queue: JoinableQueue, 
                                tags_queue: JoinableQueue, tags_return_queue: JoinableQueue,
                                settings_menu_queue: JoinableQueue, settings_menu_return_queue: JoinableQueue,
                                frontend_queue: JoinableQueue, frontend_return_queue: JoinableQueue,
                                immediate_queue: JoinableQueue, immediate_return_queue: JoinableQueue,
                                state_queue: JoinableQueue,
                                performance_queue: JoinableQueue, performance_return_queue: JoinableQueue
                                ) -> object:
        instance = super().__new__(cls)
        instance.path = path
        
        instance.return_queue = return_queue
        instance.plugins_queue = plugins_queue
        instance.plugins_return_queue = plugins_return_queue
        instance.settings_menu_queue = settings_menu_queue
        instance.settings_menu_return_queue = settings_menu_return_queue
        instance.frontend_queue = frontend_queue
        instance.frontend_return_queue = frontend_return_queue
        instance.immediate_queue = immediate_queue
        instance.immediate_return_queue = immediate_return_queue
        instance.state_queue = state_queue
        instance.performance_queue = performance_queue
        instance.performance_return_queue = performance_return_queue
        
        instance.plugins = Plugins(plugins_queue, plugins_return_queue)
        instance.globals = Global(tags_queue, tags_return_queue)
        instance.state = State(state_queue)
        
        instance.ensure_settings_file()
        instance.settings = Settings(path)
        
        if type(instance.author) != list:
            instance.author = [instance.author]
        
        return instance
   
    def load_modules(self) -> None:
        self.modules = SimpleNamespace()
        module_names = self.description.modules
        for module_name in module_names:
            module_path = f"modules/{module_name}/main.py"
            if os.path.exists(module_path):
                python_object = importlib.import_module(module_path.replace("/", ".").replace(".py", ""))
                module = python_object.Module(self)
                setattr(self.modules, module_name, module)
            else:
                logging.warning(f"Module '{module}' not found in '{module_path}'")
    
    def __init__(self, *args) -> None:
        self.ensure_functions()
        self.load_modules()
        
        if "settings_menu" in dir(type(self)) and self.settings_menu != None:
            self.settings_menu.plugin = self

        threading.Thread(target=self.settings_menu_thread, daemon=True).start()
        threading.Thread(target=self.frontend_thread, daemon=True).start()
        threading.Thread(target=self.performance_thread, daemon=True).start()

        self.imports()
        
        try: self.init()
        except Exception as ex:
            if type(ex) != AttributeError: 
                logging.exception("Error in 'init' function")
        try: self.initialize()
        except Exception as ex:
            if type(ex) != AttributeError: 
                logging.exception("Error in 'initialize' function")
        try: self.Initialize()
        except Exception as ex:
            if type(ex) != AttributeError: 
                logging.exception("Error in 'Initialize' function")

        while True:
            self.plugin()
    
    def settings_menu_thread(self):
        if "settings_menu" in dir(type(self)) and self.settings_menu != None:
            while True:
                self.settings_menu_queue.get()
                self.settings_menu_queue.task_done()
                self.settings_menu_return_queue.put(self.settings_menu.render())
    
    def frontend_thread(self):
        while True:
            data = self.frontend_queue.get()
            
            try:
                if data["operation"] == "function":
                    args = data["args"]
                    kwargs = data["kwargs"]
                    if args != ([], {}):
                        if kwargs != {}:
                            getattr(self, data["target"])(*args, **kwargs)
                        else:
                            getattr(self, data["target"])(*args)
                    elif kwargs != {}:
                        getattr(self, data["target"])(**kwargs)
                    else:
                        getattr(self, data["target"])()
            except:
                pass
            
            self.frontend_queue.task_done()
            self.frontend_return_queue.put(None)
            
    def performance_thread(self):
        while True:
            self.performance_queue.get()
            
            last_30_seconds = time.time() - 30
            self.performance = [x for x in self.performance if x[0] > last_30_seconds]
            
            self.performance_queue.task_done()
            self.performance_return_queue.put(self.performance)
            
    def notify(self, text: str, type: Literal["info", "warning", "error", "success"] = "info"):
        self.immediate_queue.put({
            "operation": "notify", 
            "options": {
                "text": text,
                "type": type
            }    
        })
        data = self.immediate_return_queue.get()
        self.immediate_return_queue.task_done()
        return data    
    
    def ask(self, text: str, options: list, description: str = "") -> str:
        self.immediate_queue.put({
            "operation": "ask", 
            "options": {
                "text": text,
                "description": description,
                "options": options
            }
        })
        return self.immediate_return_queue.get()["response"]

    def dialog(self, dialog: object) -> dict:
        self.immediate_queue.put({
            "operation": "dialog", 
            "options": dialog.build()
        })
        return self.immediate_return_queue.get()

    def plugin(self) -> None:
        self.before()
        data = self.run()
        self.after(data)
            
    def before(self) -> None:
        self.start_time = time.time()
        
    def after(self, data) -> None:
        if data is not None:
            self.return_queue.put(data, block=True)

        self.end_time = time.time()
        time_to_sleep = max(1/self.fps_cap - (self.end_time - self.start_time), 0)
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)
        
        self.performance.append((self.start_time, time.time() - self.start_time))

class PluginRunner:
    def __init__(self, plugin_name: str, plugin_description: PluginDescription, 
                    return_queue: JoinableQueue, 
                    plugins_queue: JoinableQueue, plugins_return_queue: JoinableQueue,
                    tags_queue: JoinableQueue, tags_return_queue: JoinableQueue,
                    settings_menu_queue: JoinableQueue, settings_menu_return_queue: JoinableQueue,
                    frontend_queue: JoinableQueue, frontend_return_queue: JoinableQueue,
                    immediate_queue: JoinableQueue, immediate_return_queue: JoinableQueue,
                    state_queue: JoinableQueue,
                    performance_queue: JoinableQueue, performance_return_queue: JoinableQueue
                    ):
        
        SetupProcessLogging(
            plugin_name,
            filepath=os.path.join(os.getcwd(), "logs", f"{plugin_name}.log"),
            console_level=logging.WARNING
        )
        
        self.plugin_name = plugin_name
        self.plugin_description = plugin_description
        
        self.return_queue = return_queue
        self.plugins_queue = plugins_queue
        self.plugins_return_queue = plugins_return_queue
        self.tags_queue = tags_queue
        self.tags_return_queue = tags_return_queue
        self.settings_menu_queue = settings_menu_queue
        self.settings_menu_return_queue = settings_menu_return_queue
        self.frontend_queue = frontend_queue
        self.frontend_return_queue = frontend_return_queue
        self.immediate_queue = immediate_queue
        self.immediate_return_queue = immediate_return_queue
        self.state_queue = state_queue
        self.performance_queue = performance_queue
        self.performance_return_queue = performance_return_queue

        sys.path.append(os.path.join(os.getcwd(), "plugins", plugin_name))

        try:
            # Import the plugin module
            plugin_module = importlib.import_module(f"plugins.{plugin_name}.main")

            # Instantiate the Plugin class
            if hasattr(plugin_module, 'Plugin'):
                self.plugin_instance = plugin_module.Plugin(f"plugins/{plugin_name}", return_queue, 
                                                                plugins_queue, plugins_return_queue, 
                                                                tags_queue, tags_return_queue,
                                                                settings_menu_queue, settings_menu_return_queue,
                                                                frontend_queue, frontend_return_queue,
                                                                immediate_queue, immediate_return_queue,
                                                                state_queue,
                                                                performance_queue, performance_return_queue
                                                                )
            else:
                raise ImportError(f"No class 'Plugin' found in module 'plugins.{plugin_name}.main'")
        except:
            logging.exception(f"Error loading plugin '{plugin_name}'")