#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Management Routes - Gerenciamento de APIs em tempo real
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any
from services.enhanced_api_rotation_manager import enhanced_api_rotation_manager
from services.progress_manager import progress_manager

logger = logging.getLogger(__name__)

api_management_bp = Blueprint('api_management', __name__)

@api_management_bp.route('/api/apis/status', methods=['GET'])
def get_apis_status():
    """Obtém status de todas as APIs"""
    try:
        service = request.args.get('service')
        status = enhanced_api_rotation_manager.get_api_status(service)
        
        return jsonify({
            'success': True,
            'status': status,
            'timestamp': enhanced_api_rotation_manager.last_health_check
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter status das APIs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/apis/rotate', methods=['POST'])
def rotate_api():
    """Força rotação de API para um serviço"""
    try:
        data = request.get_json()
        service = data.get('service')
        
        if not service:
            return jsonify({
                'success': False,
                'error': 'Serviço não especificado'
            }), 400
        
        new_api = enhanced_api_rotation_manager.rotate_api(service)
        
        if new_api:
            return jsonify({
                'success': True,
                'message': f'API rotacionada para {new_api.name}',
                'current_api': {
                    'name': new_api.name,
                    'status': new_api.status.value,
                    'requests_made': new_api.requests_made
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nenhuma API disponível para rotação'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao rotar API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/apis/update', methods=['POST'])
def update_api_key():
    """Atualiza chave de API em tempo real"""
    try:
        data = request.get_json()
        service = data.get('service')
        api_name = data.get('api_name')
        new_key = data.get('api_key')
        
        if not all([service, api_name, new_key]):
            return jsonify({
                'success': False,
                'error': 'Parâmetros obrigatórios: service, api_name, api_key'
            }), 400
        
        success = enhanced_api_rotation_manager.update_api_key(service, api_name, new_key)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Chave atualizada para {api_name}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'API não encontrada'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar chave da API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/apis/add', methods=['POST'])
def add_api_key():
    """Adiciona nova chave de API"""
    try:
        data = request.get_json()
        service = data.get('service')
        api_key = data.get('api_key')
        base_url = data.get('base_url')
        
        if not all([service, api_key]):
            return jsonify({
                'success': False,
                'error': 'Parâmetros obrigatórios: service, api_key'
            }), 400
        
        api_name = enhanced_api_rotation_manager.add_api_key(service, api_key, base_url)
        
        return jsonify({
            'success': True,
            'message': f'Nova API adicionada: {api_name}',
            'api_name': api_name
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/apis/remove', methods=['DELETE'])
def remove_api_key():
    """Remove chave de API"""
    try:
        data = request.get_json()
        service = data.get('service')
        api_name = data.get('api_name')
        
        if not all([service, api_name]):
            return jsonify({
                'success': False,
                'error': 'Parâmetros obrigatórios: service, api_name'
            }), 400
        
        success = enhanced_api_rotation_manager.remove_api_key(service, api_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'API removida: {api_name}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'API não encontrada'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao remover API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/apis/reset-errors', methods=['POST'])
def reset_api_errors():
    """Reseta contadores de erro das APIs"""
    try:
        data = request.get_json() or {}
        service = data.get('service')
        
        enhanced_api_rotation_manager.reset_api_errors(service)
        
        return jsonify({
            'success': True,
            'message': f'Erros resetados para {service or "todos os serviços"}'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao resetar erros: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/progress/pause', methods=['POST'])
def pause_progress():
    """Pausa execução em andamento"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'session_id é obrigatório'
            }), 400
        
        success = progress_manager.pause_session(session_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Sessão {session_id} pausada'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada ou não pode ser pausada'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao pausar progresso: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/progress/resume', methods=['POST'])
def resume_progress():
    """Resume execução pausada"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'session_id é obrigatório'
            }), 400
        
        success = progress_manager.resume_session(session_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Sessão {session_id} resumida'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada ou não está pausada'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao resumir progresso: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/progress/status/<session_id>', methods=['GET'])
def get_progress_status(session_id):
    """Obtém status do progresso"""
    try:
        status = progress_manager.get_session_progress(session_id)
        
        if status:
            return jsonify({
                'success': True,
                'progress': status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao obter status do progresso: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/progress/checkpoints/<session_id>', methods=['GET'])
def get_session_checkpoints(session_id):
    """Lista checkpoints de uma sessão"""
    try:
        checkpoints = progress_manager.list_session_checkpoints(session_id)
        
        return jsonify({
            'success': True,
            'checkpoints': checkpoints
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar checkpoints: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/progress/continue', methods=['POST'])
def continue_from_checkpoint():
    """Continua execução a partir de um checkpoint"""
    try:
        data = request.get_json()
        checkpoint_id = data.get('checkpoint_id')
        
        if not checkpoint_id:
            return jsonify({
                'success': False,
                'error': 'checkpoint_id é obrigatório'
            }), 400
        
        result = progress_manager.continue_from_checkpoint(checkpoint_id)
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Execução continuada do checkpoint',
                'session_id': result['session_id'],
                'progress': result['progress']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Checkpoint não encontrado'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao continuar do checkpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_management_bp.route('/api/progress/save', methods=['POST'])
def save_progress():
    """Salva progresso atual como checkpoint"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        current_step = data.get('current_step', 'manual_save')
        step_index = data.get('step_index', 0)
        state_data = data.get('state_data', {})
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'session_id é obrigatório'
            }), 400
        
        checkpoint_id = progress_manager.create_checkpoint(
            session_id=session_id,
            current_step=current_step,
            step_index=step_index,
            state_data=state_data,
            next_action="manual_continue",
            metadata={'save_type': 'manual'}
        )
        
        return jsonify({
            'success': True,
            'message': 'Progresso salvo',
            'checkpoint_id': checkpoint_id
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar progresso: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

