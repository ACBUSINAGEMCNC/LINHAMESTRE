/**
 * Sistema de Notificações para Apontamentos
 * Gerencia alertas, notificações e feedback visual
 */

class ApontamentoNotifications {
    constructor() {
        this.notifications = [];
        this.init();
    }

    init() {
        // Criar container de notificações se não existir
        if (!document.getElementById('notification-container')) {
            const container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }

        // Verificar notificações pendentes a cada 30 segundos
        setInterval(() => {
            this.checkPendingNotifications();
        }, 30000);
    }

    /**
     * Mostrar notificação de sucesso
     */
    showSuccess(message, title = 'Sucesso') {
        this.showNotification(message, 'success', title, 5000);
    }

    /**
     * Mostrar notificação de erro
     */
    showError(message, title = 'Erro') {
        this.showNotification(message, 'danger', title, 8000);
    }

    /**
     * Mostrar notificação de aviso
     */
    showWarning(message, title = 'Atenção') {
        this.showNotification(message, 'warning', title, 6000);
    }

    /**
     * Mostrar notificação de informação
     */
    showInfo(message, title = 'Informação') {
        this.showNotification(message, 'info', title, 5000);
    }

    /**
     * Mostrar notificação personalizada
     */
    showNotification(message, type = 'info', title = '', duration = 5000) {
        const id = 'notification-' + Date.now();
        const notification = {
            id,
            message,
            type,
            title,
            timestamp: new Date()
        };

        this.notifications.push(notification);

        const container = document.getElementById('notification-container');
        const notificationEl = this.createNotificationElement(notification);
        
        container.appendChild(notificationEl);

        // Animação de entrada
        setTimeout(() => {
            notificationEl.classList.add('show');
        }, 100);

        // Auto-remover após duração especificada
        if (duration > 0) {
            setTimeout(() => {
                this.removeNotification(id);
            }, duration);
        }

        return id;
    }

    /**
     * Criar elemento HTML da notificação
     */
    createNotificationElement(notification) {
        const div = document.createElement('div');
        div.id = notification.id;
        div.className = `alert alert-${notification.type} alert-dismissible notification-item`;
        div.style.cssText = `
            margin-bottom: 10px;
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        `;

        const icon = this.getIconForType(notification.type);
        
        div.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="me-2">
                    <i class="fas fa-${icon}"></i>
                </div>
                <div class="flex-grow-1">
                    ${notification.title ? `<strong>${notification.title}</strong><br>` : ''}
                    ${notification.message}
                    <small class="d-block text-muted mt-1">
                        ${notification.timestamp.toLocaleTimeString('pt-BR')}
                    </small>
                </div>
                <button type="button" class="btn-close" onclick="apontamentoNotifications.removeNotification('${notification.id}')"></button>
            </div>
        `;

        // Adicionar classe para animação de entrada
        div.classList.add('notification-enter');

        return div;
    }

    /**
     * Obter ícone baseado no tipo de notificação
     */
    getIconForType(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle',
            'primary': 'bell'
        };
        return icons[type] || 'bell';
    }

    /**
     * Remover notificação
     */
    removeNotification(id) {
        const element = document.getElementById(id);
        if (element) {
            element.style.transform = 'translateX(100%)';
            element.style.opacity = '0';
            
            setTimeout(() => {
                element.remove();
            }, 300);
        }

        // Remover do array
        this.notifications = this.notifications.filter(n => n.id !== id);
    }

    /**
     * Limpar todas as notificações
     */
    clearAll() {
        const container = document.getElementById('notification-container');
        if (container) {
            container.innerHTML = '';
        }
        this.notifications = [];
    }

    /**
     * Verificar notificações pendentes (exemplo: apontamentos em aberto há muito tempo)
     */
    checkPendingNotifications() {
        // Verificar se há apontamentos em aberto há mais de 4 horas
        fetch('/apontamento/api/check-pending')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.pending.length > 0) {
                    data.pending.forEach(item => {
                        this.showWarning(
                            `OS ${item.os} está ${item.status.toLowerCase()} há ${item.tempo}`,
                            'Apontamento Pendente'
                        );
                    });
                }
            })
            .catch(error => {
                console.error('Erro ao verificar notificações pendentes:', error);
            });
    }

    /**
     * Notificar sobre mudança de status
     */
    notifyStatusChange(os, oldStatus, newStatus, operador) {
        const message = `OS ${os} mudou de "${oldStatus}" para "${newStatus}" (${operador})`;
        this.showInfo(message, 'Status Atualizado');
    }

    /**
     * Notificar sobre parada prolongada
     */
    notifyLongPause(os, motivo, tempo) {
        const message = `OS ${os} está pausada há ${tempo} - Motivo: ${motivo}`;
        this.showWarning(message, 'Parada Prolongada');
    }

    /**
     * Notificar sobre meta de produção
     */
    notifyProductionGoal(os, atual, meta, percentual) {
        if (percentual >= 100) {
            this.showSuccess(`OS ${os} atingiu a meta! ${atual}/${meta} peças (${percentual}%)`, 'Meta Atingida');
        } else if (percentual >= 80) {
            this.showInfo(`OS ${os} próxima da meta: ${atual}/${meta} peças (${percentual}%)`, 'Progresso');
        }
    }

    /**
     * Notificar sobre eficiência baixa
     */
    notifyLowEfficiency(os, eficiencia) {
        if (eficiencia < 70) {
            this.showWarning(`OS ${os} com eficiência baixa: ${eficiencia}%`, 'Atenção à Eficiência');
        }
    }
}

// Instância global
const apontamentoNotifications = new ApontamentoNotifications();

// Adicionar estilos CSS
const style = document.createElement('style');
style.textContent = `
    .notification-container {
        pointer-events: none;
    }
    
    .notification-item {
        pointer-events: all;
        border-left: 4px solid;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
    }
    
    .notification-item.show {
        opacity: 1 !important;
        transform: translateX(0) !important;
    }
    
    .alert-success {
        border-left-color: #198754;
    }
    
    .alert-danger {
        border-left-color: #dc3545;
    }
    
    .alert-warning {
        border-left-color: #ffc107;
    }
    
    .alert-info {
        border-left-color: #0dcaf0;
    }
    
    .notification-item:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
`;
document.head.appendChild(style);

// Exportar para uso global
window.apontamentoNotifications = apontamentoNotifications;
