reload_app = None
is_finished = False

def set_reload_function(func):
    global reload_app
    reload_app = func