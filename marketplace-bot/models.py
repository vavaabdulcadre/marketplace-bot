from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import enum

db = SQLAlchemy()

class PlanType(enum.Enum):
    BASIC = "Básico"
    MEDIUM = "Médio"
    HIGH = "Alto"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    establishments = db.relationship('Establishment', backref='owner', lazy=True)
    subscriptions = db.relationship('Subscription', backref='user', lazy=True)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_type = db.Column(db.Enum(PlanType), nullable=False, default=PlanType.HIGH)  # Trial começa no plano Alto
    is_trial = db.Column(db.Boolean, default=True)
    trial_start = db.Column(db.DateTime, default=datetime.utcnow)
    trial_end = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=7))  # 7 dias de trial
    is_active = db.Column(db.Boolean, default=True)
    last_payment_date = db.Column(db.DateTime)
    next_payment_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    payments = db.relationship('Payment', backref='subscription', lazy=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="MZN")
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(20), default="pending")  # pending, completed, failed
    transaction_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))
    establishments = db.relationship('Establishment', backref='category', lazy=True)

class Establishment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    neighborhood = db.Column(db.String(100))
    reference_point = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    phone_contact = db.Column(db.String(20))
    opening_hours = db.Column(db.String(200))
    average_rating = db.Column(db.Float, default=0.0)
    logo_url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    products = db.relationship('Product', backref='establishment', lazy=True)
    promotions = db.relationship('Promotion', backref='establishment', lazy=True)
    reviews = db.relationship('Review', backref='establishment', lazy=True)
    orders = db.relationship('Order', backref='establishment', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey('establishment.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="MZN")
    internal_category = db.Column(db.String(50))
    image_url = db.Column(db.String(200))
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

class Promotion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey('establishment.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    promotion_type = db.Column(db.String(50))  # percentage_discount, fixed_discount, buy_x_get_y_free, free_item
    discount_value = db.Column(db.Float)
    required_product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    free_product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    minimum_order_value = db.Column(db.Float)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    required_product = db.relationship('Product', foreign_keys=[required_product_id])
    free_product = db.relationship('Product', foreign_keys=[free_product_id])

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    establishment_id = db.Column(db.Integer, db.ForeignKey('establishment.id'), nullable=False)
    order_status = db.Column(db.String(50), default="pending_payment")  # pending_payment, payment_received, preparing, ready_for_pickup, out_for_delivery, delivered, cancelled
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="MZN")
    delivery_type = db.Column(db.String(20))  # delivery, pickup
    delivery_address = db.Column(db.String(200))
    delivery_neighborhood = db.Column(db.String(100))
    delivery_reference_point = db.Column(db.String(200))
    delivery_contact_phone = db.Column(db.String(20))
    delivery_time_preference = db.Column(db.String(50))
    delivery_fee = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(50))
    payment_status = db.Column(db.String(20), default="pending")  # pending, paid, failed
    payment_proof_url = db.Column(db.String(200))
    notes_from_user = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    items = db.relationship('OrderItem', backref='order', lazy=True)
    reviews = db.relationship('Review', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time_of_order = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    establishment_id = db.Column(db.Integer, db.ForeignKey('establishment.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    rating = db.Column(db.Integer, nullable=False)  # 1 a 5 estrelas
    comment = db.Column(db.Text)
    review_status = db.Column(db.String(20), default="approved")  # pending_approval, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatbotConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey('establishment.id'), nullable=False)
    tone_of_voice = db.Column(db.String(50), default="friendly")  # formal, friendly, casual
    welcome_message = db.Column(db.Text)
    farewell_message = db.Column(db.Text)
    custom_responses = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relação
    establishment = db.relationship('Establishment', backref='chatbot_config', uselist=False)

class ChatFlow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey('establishment.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    flow_data = db.Column(db.JSON, nullable=False)  # Armazena a estrutura do fluxo em JSON
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relação
    establishment = db.relationship('Establishment', backref='chat_flows')
