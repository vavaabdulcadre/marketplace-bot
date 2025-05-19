from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, User, Establishment, Product, Promotion, Order, Review, Subscription, Payment, ChatFlow, ChatbotConfig, PlanType
from datetime import datetime, timedelta
import json

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/')
@login_required
def index():
    """Dashboard principal do lojista"""
    # Verificar se o usuário tem uma assinatura ativa
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    if not subscription:
        # Redirecionar para página de escolha de plano se não tiver assinatura
        return redirect(url_for('dashboard.choose_plan'))
    
    # Calcular dias restantes do trial
    days_left = 0
    trial_banner = False
    
    if subscription.is_trial:
        days_left = (subscription.trial_end - datetime.utcnow()).days
        if days_left < 0:
            days_left = 0
        trial_banner = True
    
    # Buscar estabelecimentos do usuário
    establishments = Establishment.query.filter_by(owner_id=current_user.id).all()
    
    # Buscar estatísticas para o dashboard
    stats = {
        'total_orders': 0,
        'total_revenue': 0,
        'avg_rating': 0,
        'total_customers': 0
    }
    
    for establishment in establishments:
        # Contar pedidos dos últimos 30 dias
        recent_orders = Order.query.filter_by(
            establishment_id=establishment.id
        ).filter(
            Order.created_at >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        stats['total_orders'] += len(recent_orders)
        stats['total_revenue'] += sum(order.total_amount for order in recent_orders)
        
        # Calcular avaliação média
        if establishment.reviews:
            stats['avg_rating'] = sum(review.rating for review in establishment.reviews) / len(establishment.reviews)
        
        # Contar clientes únicos
        unique_customers = set(order.user_id for order in recent_orders)
        stats['total_customers'] += len(unique_customers)
    
    return render_template(
        'dashboard/index.html',
        subscription=subscription,
        days_left=days_left,
        trial_banner=trial_banner,
        establishments=establishments,
        stats=stats
    )

@dashboard.route('/choose-plan')
@login_required
def choose_plan():
    """Página de escolha de plano"""
    # Verificar se o usuário já tem uma assinatura
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    # Definir os planos disponíveis
    plans = {
        'basic': {
            'name': 'Básico',
            'price': 500,
            'features': [
                '5 Fluxos de Conversa',
                'WhatsApp + 1 plataforma',
                'Suporte por E-mail'
            ]
        },
        'medium': {
            'name': 'Médio',
            'price': 1000,
            'features': [
                '15 Fluxos de Conversa',
                '3 plataformas',
                'IA Preditiva Básica',
                'Suporte por E-mail + Chat'
            ]
        },
        'high': {
            'name': 'Alto',
            'price': 2500,
            'features': [
                'Fluxos de Conversa Ilimitados',
                'Todas as plataformas + API personalizada',
                'IA Preditiva Avançada',
                'Suporte 24/7 Prioritário'
            ]
        }
    }
    
    return render_template(
        'dashboard/choose_plan.html',
        subscription=subscription,
        plans=plans
    )

@dashboard.route('/select-plan/<plan_type>', methods=['POST'])
@login_required
def select_plan(plan_type):
    """Selecionar um plano"""
    # Mapear o tipo de plano para o enum
    plan_mapping = {
        'basic': PlanType.BASIC,
        'medium': PlanType.MEDIUM,
        'high': PlanType.HIGH
    }
    
    if plan_type not in plan_mapping:
        flash('Plano inválido', 'error')
        return redirect(url_for('dashboard.choose_plan'))
    
    # Verificar se o usuário já tem uma assinatura
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    if subscription:
        # Atualizar a assinatura existente
        old_plan = subscription.plan_type
        subscription.plan_type = plan_mapping[plan_type]
        subscription.updated_at = datetime.utcnow()
        
        # Se estiver saindo do trial, definir datas de pagamento
        if subscription.is_trial:
            subscription.is_trial = False
            subscription.last_payment_date = datetime.utcnow()
            subscription.next_payment_date = datetime.utcnow() + timedelta(days=30)
    else:
        # Criar uma nova assinatura
        subscription = Subscription(
            user_id=current_user.id,
            plan_type=plan_mapping[plan_type],
            is_trial=False,
            last_payment_date=datetime.utcnow(),
            next_payment_date=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(subscription)
    
    # Criar um registro de pagamento
    plan_prices = {
        PlanType.BASIC: 500,
        PlanType.MEDIUM: 1000,
        PlanType.HIGH: 2500
    }
    
    payment = Payment(
        subscription_id=subscription.id,
        amount=plan_prices[subscription.plan_type],
        payment_method='credit_card',  # Placeholder
        status='completed'
    )
    db.session.add(payment)
    
    db.session.commit()
    
    flash(f'Plano {plan_mapping[plan_type].value} selecionado com sucesso!', 'success')
    return redirect(url_for('dashboard.index'))

@dashboard.route('/establishments')
@login_required
def establishments():
    """Listar estabelecimentos do lojista"""
    establishments = Establishment.query.filter_by(owner_id=current_user.id).all()
    return render_template('dashboard/establishments.html', establishments=establishments)

@dashboard.route('/establishments/new', methods=['GET', 'POST'])
@login_required
def new_establishment():
    """Criar novo estabelecimento"""
    if request.method == 'POST':
        # Verificar limite de estabelecimentos com base no plano
        subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
        if not subscription:
            flash('Você precisa escolher um plano para criar estabelecimentos', 'error')
            return redirect(url_for('dashboard.choose_plan'))
        
        # Contar estabelecimentos existentes
        establishment_count = Establishment.query.filter_by(owner_id=current_user.id).count()
        
        # Verificar limites por plano
        if subscription.plan_type == PlanType.BASIC and establishment_count >= 1:
            flash('Seu plano Básico permite apenas 1 estabelecimento', 'error')
            return redirect(url_for('dashboard.establishments'))
        elif subscription.plan_type == PlanType.MEDIUM and establishment_count >= 3:
            flash('Seu plano Médio permite apenas 3 estabelecimentos', 'error')
            return redirect(url_for('dashboard.establishments'))
        
        # Criar novo estabelecimento
        establishment = Establishment(
            owner_id=current_user.id,
            category_id=request.form.get('category_id'),
            name=request.form.get('name'),
            description=request.form.get('description'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            neighborhood=request.form.get('neighborhood'),
            reference_point=request.form.get('reference_point'),
            phone_contact=request.form.get('phone_contact'),
            opening_hours=request.form.get('opening_hours')
        )
        
        db.session.add(establishment)
        db.session.commit()
        
        # Criar configuração padrão do chatbot
        chatbot_config = ChatbotConfig(
            establishment_id=establishment.id,
            welcome_message=f"Olá! Bem-vindo(a) a {establishment.name}. Como posso ajudar?",
            farewell_message="Obrigado por escolher nossos produtos. Volte sempre!"
        )
        
        db.session.add(chatbot_config)
        db.session.commit()
        
        flash('Estabelecimento criado com sucesso!', 'success')
        return redirect(url_for('dashboard.establishments'))
    
    # GET: Mostrar formulário
    from models import Category
    categories = Category.query.all()
    return render_template('dashboard/new_establishment.html', categories=categories)

@dashboard.route('/establishments/<int:id>')
@login_required
def view_establishment(id):
    """Ver detalhes de um estabelecimento"""
    establishment = Establishment.query.get_or_404(id)
    
    # Verificar se o estabelecimento pertence ao usuário logado
    if establishment.owner_id != current_user.id:
        flash('Você não tem permissão para acessar este estabelecimento', 'error')
        return redirect(url_for('dashboard.establishments'))
    
    return render_template('dashboard/view_establishment.html', establishment=establishment)

@dashboard.route('/chatbot-editor/<int:establishment_id>')
@login_required
def chatbot_editor(establishment_id):
    """Editor visual de fluxos do chatbot"""
    establishment = Establishment.query.get_or_404(establishment_id)
    
    # Verificar se o estabelecimento pertence ao usuário logado
    if establishment.owner_id != current_user.id:
        flash('Você não tem permissão para acessar este estabelecimento', 'error')
        return redirect(url_for('dashboard.establishments'))
    
    # Buscar fluxos existentes
    flows = ChatFlow.query.filter_by(establishment_id=establishment_id).all()
    
    # Verificar limite de fluxos com base no plano
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    flow_limit = float('inf')  # Ilimitado por padrão (plano Alto)
    if subscription.plan_type == PlanType.BASIC:
        flow_limit = 5
    elif subscription.plan_type == PlanType.MEDIUM:
        flow_limit = 15
    
    can_create_flow = len(flows) < flow_limit
    
    return render_template(
        'dashboard/chatbot_editor.html',
        establishment=establishment,
        flows=flows,
        can_create_flow=can_create_flow,
        flow_limit=flow_limit
    )

@dashboard.route('/chatbot-editor/<int:establishment_id>/flow/new', methods=['GET', 'POST'])
@login_required
def new_flow(establishment_id):
    """Criar novo fluxo de chatbot"""
    establishment = Establishment.query.get_or_404(establishment_id)
    
    # Verificar se o estabelecimento pertence ao usuário logado
    if establishment.owner_id != current_user.id:
        flash('Você não tem permissão para acessar este estabelecimento', 'error')
        return redirect(url_for('dashboard.establishments'))
    
    # Verificar limite de fluxos com base no plano
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    flows = ChatFlow.query.filter_by(establishment_id=establishment_id).all()
    
    flow_limit = float('inf')  # Ilimitado por padrão (plano Alto)
    if subscription.plan_type == PlanType.BASIC:
        flow_limit = 5
    elif subscription.plan_type == PlanType.MEDIUM:
        flow_limit = 15
    
    if len(flows) >= flow_limit:
        flash(f'Seu plano permite apenas {flow_limit} fluxos de conversa', 'error')
        return redirect(url_for('dashboard.chatbot_editor', establishment_id=establishment_id))
    
    if request.method == 'POST':
        # Criar novo fluxo
        flow = ChatFlow(
            establishment_id=establishment_id,
            name=request.form.get('name'),
            description=request.form.get('description'),
            flow_data=json.loads(request.form.get('flow_data', '{}'))
        )
        
        db.session.add(flow)
        db.session.commit()
        
        flash('Fluxo criado com sucesso!', 'success')
        return redirect(url_for('dashboard.chatbot_editor', establishment_id=establishment_id))
    
    # GET: Mostrar formulário
    return render_template('dashboard/new_flow.html', establishment=establishment)

@dashboard.route('/chatbot-editor/<int:establishment_id>/flow/<int:flow_id>', methods=['GET', 'POST'])
@login_required
def edit_flow(establishment_id, flow_id):
    """Editar fluxo de chatbot existente"""
    establishment = Establishment.query.get_or_404(establishment_id)
    flow = ChatFlow.query.get_or_404(flow_id)
    
    # Verificar se o estabelecimento pertence ao usuário logado
    if establishment.owner_id != current_user.id:
        flash('Você não tem permissão para acessar este estabelecimento', 'error')
        return redirect(url_for('dashboard.establishments'))
    
    # Verificar se o fluxo pertence ao estabelecimento
    if flow.establishment_id != establishment_id:
        flash('Este fluxo não pertence ao estabelecimento selecionado', 'error')
        return redirect(url_for('dashboard.chatbot_editor', establishment_id=establishment_id))
    
    if request.method == 'POST':
        # Atualizar fluxo
        flow.name = request.form.get('name')
        flow.description = request.form.get('description')
        flow.flow_data = json.loads(request.form.get('flow_data', '{}'))
        flow.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Fluxo atualizado com sucesso!', 'success')
        return redirect(url_for('dashboard.chatbot_editor', establishment_id=establishment_id))
    
    # GET: Mostrar formulário de edição
    return render_template('dashboard/edit_flow.html', establishment=establishment, flow=flow)

@dashboard.route('/orders')
@login_required
def orders():
    """Listar pedidos de todos os estabelecimentos do lojista"""
    # Buscar estabelecimentos do usuário
    establishments = Establishment.query.filter_by(owner_id=current_user.id).all()
    establishment_ids = [e.id for e in establishments]
    
    # Buscar pedidos dos estabelecimentos
    orders = Order.query.filter(Order.establishment_id.in_(establishment_ids)).order_by(Order.created_at.desc()).all()
    
    return render_template('dashboard/orders.html', orders=orders, establishments=establishments)

@dashboard.route('/orders/<int:id>')
@login_required
def view_order(id):
    """Ver detalhes de um pedido"""
    order = Order.query.get_or_404(id)
    
    # Verificar se o pedido pertence a um estabelecimento do usuário
    establishment = Establishment.query.get(order.establishment_id)
    if establishment.owner_id != current_user.id:
        flash('Você não tem permissão para acessar este pedido', 'error')
        return redirect(url_for('dashboard.orders'))
    
    return render_template('dashboard/view_order.html', order=order)

@dashboard.route('/orders/<int:id>/update-status', methods=['POST'])
@login_required
def update_order_status(id):
    """Atualizar status de um pedido"""
    order = Order.query.get_or_404(id)
    
    # Verificar se o pedido pertence a um estabelecimento do usuário
    establishment = Establishment.query.get(order.establishment_id)
    if establishment.owner_id != current_user.id:
        flash('Você não tem permissão para atualizar este pedido', 'error')
        return redirect(url_for('dashboard.orders'))
    
    new_status = request.form.get('status')
    valid_statuses = ['pending_payment', 'payment_received', 'preparing', 'ready_for_pickup', 'out_for_delivery', 'delivered', 'cancelled']
    
    if new_status in valid_statuses:
        order.order_status = new_status
        order.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Status do pedido atualizado com sucesso!', 'success')
    else:
        flash('Status inválido', 'error')
    
    return redirect(url_for('dashboard.view_order', id=id))

@dashboard.route('/analytics')
@login_required
def analytics():
    """Página de análise de dados e métricas"""
    # Buscar estabelecimentos do usuário
    establishments = Establishment.query.filter_by(owner_id=current_user.id).all()
    establishment_ids = [e.id for e in establishments]
    
    # Definir período de análise (últimos 30 dias por padrão)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Buscar pedidos do período
    orders = Order.query.filter(
        Order.establishment_id.in_(establishment_ids),
        Order.created_at.between(start_date, end_date)
    ).all()
    
    # Calcular métricas
    total_orders = len(orders)
    total_revenue = sum(order.total_amount for order in orders)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    # Dados para gráficos
    daily_revenue = {}
    daily_orders = {}
    
    for order in orders:
        date_str = order.created_at.strftime('%Y-%m-%d')
        
        if date_str not in daily_revenue:
            daily_revenue[date_str] = 0
            daily_orders[date_str] = 0
        
        daily_revenue[date_str] += order.total_amount
        daily_orders[date_str] += 1
    
    # Ordenar por data
    dates = sorted(daily_revenue.keys())
    revenue_data = [daily_revenue[date] for date in dates]
    orders_data = [daily_orders[date] for date in dates]
    
    return render_template(
        'dashboard/analytics.html',
        total_orders=total_orders,
        total_revenue=total_revenue,
        avg_order_value=avg_order_value,
        dates=dates,
        revenue_data=revenue_data,
        orders_data=orders_data
    )

@dashboard.route('/settings')
@login_required
def settings():
    """Configurações da conta e assinatura"""
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    return render_template('dashboard/settings.html', subscription=subscription)

@dashboard.route('/settings/update-profile', methods=['POST'])
@login_required
def update_profile():
    """Atualizar perfil do usuário"""
    current_user.name = request.form.get('name')
    current_user.phone = request.form.get('phone')
    current_user.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Perfil atualizado com sucesso!', 'success')
    return redirect(url_for('dashboard.settings'))

@dashboard.route('/settings/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancelar assinatura"""
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    if subscription:
        subscription.is_active = False
        subscription.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Assinatura cancelada com sucesso', 'success')
    else:
        flash('Você não possui uma assinatura ativa', 'error')
    
    return redirect(url_for('dashboard.settings'))

@dashboard.route('/onboarding')
@login_required
def onboarding():
    """Página de onboarding para novos usuários"""
    return render_template('dashboard/onboarding.html')

@dashboard.route('/api/trial-status')
@login_required
def trial_status():
    """API para verificar o status do trial (usado pelo frontend)"""
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    if not subscription:
        return jsonify({
            'is_trial': False,
            'days_left': 0,
            'trial_expired': True
        })
    
    if not subscription.is_trial:
        return jsonify({
            'is_trial': False,
            'days_left': 0,
            'trial_expired': False
        })
    
    days_left = (subscription.trial_end - datetime.utcnow()).days
    if days_left < 0:
        days_left = 0
    
    return jsonify({
        'is_trial': True,
        'days_left': days_left,
        'trial_expired': days_left <= 0
    })
