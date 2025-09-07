#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Progress Manager - Sistema de Controle de Progresso
Permite pausar, salvar e continuar execuções em qualquer ponto
"""

import os
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import pickle
import uuid

logger = logging.getLogger(__name__)

class ExecutionState(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

@dataclass
class ProgressCheckpoint:
    session_id: str
    checkpoint_id: str
    timestamp: float
    current_step: str
    step_index: int
    total_steps: int
    progress_percentage: float
    state_data: Dict[str, Any]
    execution_context: Dict[str, Any]
    next_action: str
    metadata: Dict[str, Any]

class ProgressManager:
    """
    Gerenciador de progresso com capacidade de pausar/continuar execuções
    """
    
    def __init__(self):
        self.checkpoints_dir = "progress_checkpoints"
        os.makedirs(self.checkpoints_dir, exist_ok=True)
        
        self.active_sessions = {}
        self.execution_states = {}
        self.pause_flags = {}
        self.progress_callbacks = {}
        self.lock = threading.Lock()
        
        logger.info("✅ Progress Manager inicializado")
    
    def start_session(self, session_id: str, total_steps: int, context: Dict[str, Any] = None) -> str:
        """Inicia uma nova sessão de progresso"""
        with self.lock:
            self.active_sessions[session_id] = {
                'total_steps': total_steps,
                'current_step': 0,
                'started_at': time.time(),
                'context': context or {},
                'checkpoints': []
            }
            self.execution_states[session_id] = ExecutionState.RUNNING
            self.pause_flags[session_id] = False
            
        logger.info(f"🚀 Sessão de progresso iniciada: {session_id}")
        return session_id
    
    def create_checkpoint(
        self,
        session_id: str,
        current_step: str,
        step_index: int,
        state_data: Dict[str, Any],
        next_action: str = "",
        metadata: Dict[str, Any] = None
    ) -> str:
        """Cria um checkpoint do progresso atual"""
        
        if session_id not in self.active_sessions:
            raise ValueError(f"Sessão {session_id} não encontrada")
        
        session = self.active_sessions[session_id]
        checkpoint_id = f"checkpoint_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        progress_percentage = (step_index / session['total_steps']) * 100
        
        checkpoint = ProgressCheckpoint(
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            timestamp=time.time(),
            current_step=current_step,
            step_index=step_index,
            total_steps=session['total_steps'],
            progress_percentage=progress_percentage,
            state_data=state_data,
            execution_context=session['context'],
            next_action=next_action,
            metadata=metadata or {}
        )
        
        # Salva checkpoint em arquivo
        checkpoint_file = os.path.join(self.checkpoints_dir, f"{checkpoint_id}.json")
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(checkpoint), f, ensure_ascii=False, indent=2, default=str)
        
        # Salva estado binário se necessário
        if any(isinstance(v, (bytes, object)) for v in state_data.values()):
            state_file = os.path.join(self.checkpoints_dir, f"{checkpoint_id}_state.pkl")
            with open(state_file, 'wb') as f:
                pickle.dump(state_data, f)
        
        # Atualiza sessão
        session['checkpoints'].append(checkpoint_id)
        session['current_step'] = step_index
        session['last_checkpoint'] = checkpoint_id
        
        logger.info(f"💾 Checkpoint criado: {checkpoint_id} ({progress_percentage:.1f}%)")
        
        # Notifica callbacks
        self._notify_progress_callbacks(session_id, checkpoint)
        
        return checkpoint_id
    
    def pause_session(self, session_id: str) -> bool:
        """Pausa a execução de uma sessão"""
        with self.lock:
            if session_id in self.active_sessions:
                self.pause_flags[session_id] = True
                self.execution_states[session_id] = ExecutionState.PAUSED
                
                # Cria checkpoint de pausa
                session = self.active_sessions[session_id]
                self.create_checkpoint(
                    session_id=session_id,
                    current_step="PAUSED",
                    step_index=session['current_step'],
                    state_data={'paused_at': time.time()},
                    next_action="resume_execution",
                    metadata={'pause_reason': 'user_request'}
                )
                
                logger.info(f"⏸️ Sessão pausada: {session_id}")
                return True
        return False
    
    def resume_session(self, session_id: str) -> bool:
        """Resume a execução de uma sessão pausada"""
        with self.lock:
            if session_id in self.active_sessions and self.execution_states[session_id] == ExecutionState.PAUSED:
                self.pause_flags[session_id] = False
                self.execution_states[session_id] = ExecutionState.RUNNING
                
                logger.info(f"▶️ Sessão resumida: {session_id}")
                return True
        return False
    
    def is_paused(self, session_id: str) -> bool:
        """Verifica se uma sessão está pausada"""
        return self.pause_flags.get(session_id, False)
    
    def wait_if_paused(self, session_id: str, check_interval: float = 0.5):
        """Aguarda enquanto a sessão estiver pausada"""
        while self.is_paused(session_id):
            time.sleep(check_interval)
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[ProgressCheckpoint]:
        """Carrega um checkpoint específico"""
        checkpoint_file = os.path.join(self.checkpoints_dir, f"{checkpoint_id}.json")
        
        if not os.path.exists(checkpoint_file):
            return None
        
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Carrega estado binário se existir
            state_file = os.path.join(self.checkpoints_dir, f"{checkpoint_id}_state.pkl")
            if os.path.exists(state_file):
                with open(state_file, 'rb') as f:
                    binary_state = pickle.load(f)
                data['state_data'].update(binary_state)
            
            checkpoint = ProgressCheckpoint(**data)
            logger.info(f"📂 Checkpoint carregado: {checkpoint_id}")
            return checkpoint
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar checkpoint {checkpoint_id}: {e}")
            return None
    
    def continue_from_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Continua execução a partir de um checkpoint"""
        checkpoint = self.load_checkpoint(checkpoint_id)
        
        if not checkpoint:
            return None
        
        # Restaura sessão
        session_id = checkpoint.session_id
        self.active_sessions[session_id] = {
            'total_steps': checkpoint.total_steps,
            'current_step': checkpoint.step_index,
            'started_at': time.time(),
            'context': checkpoint.execution_context,
            'checkpoints': [checkpoint_id],
            'resumed_from': checkpoint_id
        }
        
        self.execution_states[session_id] = ExecutionState.RUNNING
        self.pause_flags[session_id] = False
        
        logger.info(f"🔄 Execução continuada do checkpoint: {checkpoint_id}")
        
        return {
            'session_id': session_id,
            'checkpoint': checkpoint,
            'state_data': checkpoint.state_data,
            'next_action': checkpoint.next_action,
            'progress': checkpoint.progress_percentage
        }
    
    def get_session_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtém o progresso atual de uma sessão"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        return {
            'session_id': session_id,
            'current_step': session['current_step'],
            'total_steps': session['total_steps'],
            'progress_percentage': (session['current_step'] / session['total_steps']) * 100,
            'state': self.execution_states[session_id].value,
            'is_paused': self.pause_flags.get(session_id, False),
            'checkpoints_count': len(session.get('checkpoints', [])),
            'started_at': session['started_at'],
            'elapsed_time': time.time() - session['started_at']
        }
    
    def list_session_checkpoints(self, session_id: str) -> List[Dict[str, Any]]:
        """Lista todos os checkpoints de uma sessão"""
        if session_id not in self.active_sessions:
            return []
        
        session = self.active_sessions[session_id]
        checkpoints = []
        
        for checkpoint_id in session.get('checkpoints', []):
            checkpoint = self.load_checkpoint(checkpoint_id)
            if checkpoint:
                checkpoints.append({
                    'checkpoint_id': checkpoint_id,
                    'timestamp': checkpoint.timestamp,
                    'current_step': checkpoint.current_step,
                    'progress_percentage': checkpoint.progress_percentage,
                    'next_action': checkpoint.next_action
                })
        
        return checkpoints
    
    def register_progress_callback(self, session_id: str, callback: Callable):
        """Registra callback para notificações de progresso"""
        if session_id not in self.progress_callbacks:
            self.progress_callbacks[session_id] = []
        self.progress_callbacks[session_id].append(callback)
    
    def _notify_progress_callbacks(self, session_id: str, checkpoint: ProgressCheckpoint):
        """Notifica callbacks registrados sobre progresso"""
        callbacks = self.progress_callbacks.get(session_id, [])
        for callback in callbacks:
            try:
                callback(checkpoint)
            except Exception as e:
                logger.error(f"❌ Erro em callback de progresso: {e}")
    
    def complete_session(self, session_id: str, final_data: Dict[str, Any] = None):
        """Marca uma sessão como completa"""
        with self.lock:
            if session_id in self.active_sessions:
                self.execution_states[session_id] = ExecutionState.COMPLETED
                
                # Cria checkpoint final
                session = self.active_sessions[session_id]
                self.create_checkpoint(
                    session_id=session_id,
                    current_step="COMPLETED",
                    step_index=session['total_steps'],
                    state_data=final_data or {},
                    next_action="session_complete",
                    metadata={'completed_at': time.time()}
                )
                
                logger.info(f"✅ Sessão completa: {session_id}")
    
    def cancel_session(self, session_id: str, reason: str = ""):
        """Cancela uma sessão"""
        with self.lock:
            if session_id in self.active_sessions:
                self.execution_states[session_id] = ExecutionState.CANCELLED
                self.pause_flags[session_id] = False
                
                logger.info(f"❌ Sessão cancelada: {session_id} - {reason}")
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 24):
        """Remove checkpoints antigos"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed_count = 0
        
        for filename in os.listdir(self.checkpoints_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.checkpoints_dir, filename)
                if os.path.getmtime(filepath) < cutoff_time:
                    try:
                        os.remove(filepath)
                        # Remove arquivo de estado correspondente
                        state_file = filepath.replace('.json', '_state.pkl')
                        if os.path.exists(state_file):
                            os.remove(state_file)
                        removed_count += 1
                    except Exception as e:
                        logger.error(f"❌ Erro ao remover checkpoint {filename}: {e}")
        
        if removed_count > 0:
            logger.info(f"🧹 {removed_count} checkpoints antigos removidos")

# Instância global
progress_manager = ProgressManager()

