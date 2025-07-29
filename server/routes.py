from flask import Blueprint, render_template, flash, redirect, request
from config import config
from utils import unflatten_dict, flatten_with_types

bp = Blueprint('routes', __name__, template_folder='templates', static_folder='static')

@bp.route('/')
def home():
    return render_template('index.html', config=config.get_config())

@bp.route('/update_config', methods=['POST'])
def update_config():
    try:
        type_map = flatten_with_types(config.config)

        flat = {}
        for key, val_type in type_map.items():
            raw_val = request.form.get(key)

            if val_type is bool:
                flat[key] = raw_val is not None  # checkbox only submits if checked
            elif raw_val is not None:
                try:
                    if val_type is int:
                        flat[key] = int(raw_val)
                    elif val_type is float:
                        flat[key] = float(raw_val)
                    else:
                        flat[key] = raw_val
                except ValueError:
                    flat[key] = raw_val

        config.config = unflatten_dict(flat)
        config.save_config()
        flash('Configuration updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating configuration: {e}', 'error')
    return redirect('/')