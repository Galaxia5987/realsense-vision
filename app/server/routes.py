import time
import os
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from app.config import ConfigManager
from utils import unflatten_dict, flatten_with_types, get_enum_options_by_path, restart_service
import convert_model
from app.core.reloader import reload_app
from app.config import ConfigManager
import app.scheduler as scheduler
from app.components.supervisor import supervisor
import app.core.logging_config as logging_config

logger = logging_config.get_logger('routes')

router = APIRouter()

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
router.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_FOLDER = 'uploads'


def get_uploaded_models():
    if not os.path.exists(UPLOAD_FOLDER):
        return []
    return [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('_rknn_model')]


@router.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": ConfigManager().get,
            "models": get_uploaded_models()
        }
    )


@router.post('/update_config')
async def update_config(request: Request):
    try:
        form_data = await request.form()
        
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

        type_map = flatten_with_enum_refs(ConfigManager().get().model_dump)
        flat = {}

        for key, (kind, val_type) in type_map.items():
            raw_val = form_data.get(key)

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

        config_dict = config.config.model_dump()
        recursive_update_enum_preserve(config_dict, updates)
        config.config = config.config.__class__(**config_dict)
        config.save_config()
        
        # For flash messages in FastAPI, you'd typically use session middleware
        # For now, just redirect
        return RedirectResponse(url='/', status_code=303)
    except Exception as e:
        logger.exception("Error updating configuration", operation="update_config")
        raise HTTPException(status_code=500, detail=f'Error updating configuration: {e}')


@router.post('/reload')
async def reload():
    reload_app()
    return RedirectResponse(url='/', status_code=303)


@router.post('/restart')
async def restart():
    restart_service()
    return RedirectResponse(url='/', status_code=303)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == "pt"


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail='No selected file')
        
        if not allowed_file(file.filename):
            raise HTTPException(status_code=400, detail='Invalid file type. Only .pt files allowed')
        
        filename = secure_filename(file.filename)
        
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        if not filename.endswith(".pt"):
            filename += ".pt"
        
        file_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        time.sleep(1)
        chip = config.config.rknn_chip_type
        scheduler.scheduler.add_job(
            convert_model.convert_model,
            'date',
            run_date=None,
            kwargs={
                "model_path": file_path,
                "chip": chip,
                "flash_after": True
            },
            id=f"convert_model_{filename}"
        )
        
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.exception("Model conversion failed", operation="upload")
        raise HTTPException(status_code=500, detail=f'Error converting model: {e}')


@router.get('/health')
async def health():
    """Health check endpoint showing system status."""
    try:
        health_summary = supervisor.get_system_health_summary()
        return JSONResponse(content=health_summary, status_code=200)
    except Exception as e:
        logger.exception("Error getting health status", operation="health")
        return JSONResponse(
            content={
                'status': 'error',
                'message': str(e)
            },
            status_code=500
        )