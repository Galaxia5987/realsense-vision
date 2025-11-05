import time
from flask import Blueprint, render_template, flash, redirect, request, jsonify
from config import config
from utils import unflatten_dict, flatten_with_types, get_enum_options_by_path, restart_service
from werkzeug.utils import secure_filename
import os
import convert_model
from reloader import reload_app
import scheduler
from supervisor import supervisor
import logging_config

logger = logging_config.get_logger('routes')

bp = Blueprint('routes', __name__, template_folder='templates', static_folder='static')
UPLOAD_FOLDER = 'uploads'

def get_uploaded_models():
    if not os.path.exists(UPLOAD_FOLDER):
        return []
    return [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('_rknn_model')]

@bp.route('/')
def home():
    return render_template('index.html', config=config.get_config(), models=get_uploaded_models())

@bp.route('/update_config', methods=['POST'])
def update_config():
    try:
            
        def flatten_with_enum_refs(d, parent_key='', sep='.'):
            items = {}
            for k, v in d.items():
                full_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict) and 'enum' in v and 'value' in v:
                    items[full_key + '.value'] = ('enum', type(v['value']))
                elif isinstance(v, dict):
                    items.update(flatten_with_enum_refs(v, full_key, sep))
                else:
                    items[full_key] = ('normal', type(v))
            return items

        type_map = flatten_with_enum_refs(config.config)
        flat = {}

        # Just the values from the form
        for key, (kind, val_type) in type_map.items():
            raw_val = request.form.get(key)

            if kind == 'normal':
                if val_type is bool:
                    flat[key] = raw_val is not None
                elif raw_val is not None:
                    try:
                        flat[key] = int(raw_val) if val_type is int else (
                            float(raw_val) if val_type is float else raw_val
                        )
                    except ValueError:
                        flat[key] = raw_val

            elif kind == 'enum' and raw_val is not None:
                flat[key] = raw_val

        updates = unflatten_dict(flat)
        def recursive_update_enum_preserve(cfg, upd):
            for k, v in upd.items():
                if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                    recursive_update_enum_preserve(cfg[k], v)
                elif k == 'value' and 'enum' in cfg:
                    cfg['value'] = v
                else:
                    cfg[k] = v

        recursive_update_enum_preserve(config.config, updates)
        config.save_config()
        flash('Configuration updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating configuration: {e}', 'error')
    return redirect('/')

@bp.route('/reload', methods=['POST'])
def reload():
    global reload_app
    reload_app()
    return redirect('/')

@bp.route('/restart', methods=['POST'])
def restart():
    return redirect('/')

@bp.after_request
def mid(response):
    if request.path == "/restart":
        restart_service()
    return response

    


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() == "pt"

@bp.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect("/")
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect("/")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename if file.filename else "model.pt")
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        if not filename.endswith(".pt"):
            filename += ".pt"
        if os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
            os.remove(os.path.join(UPLOAD_FOLDER, filename))
        file.save(os.path.abspath(os.path.join(UPLOAD_FOLDER, filename)))
        try:
            time.sleep(1)
            chip = config.get_config().get("rknn_chip_type", "rk3588")
            scheduler.scheduler.add_job(convert_model.convert_model, 'date', run_date=None, kwargs={"model_path":os.path.abspath(os.path.join(UPLOAD_FOLDER, filename)), "chip": chip, "flash_after": True}, id=f"convert_model_{filename}")
            
        except Exception as e:
            flash(f'Error converting model: {e}', 'error')
            logger.exception("Model conversion failed", operation="upload")
        return redirect("/")
    return redirect("/")

@bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint showing system status."""
    try:
        health_summary = supervisor.get_system_health_summary()
        return jsonify(health_summary), 200
    except Exception as e:
        logger.exception("Error getting health status", operation="health")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500