from flask import Flask, request, jsonify
import os
import json
import dialogflow
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Carregar dados dos estabelecimentos
with open('dados_estabelecimentos.json', 'r', encoding='utf-8') as f:
    estabelecimentos_data = json.load(f)

# Configuração do Twilio
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'ACcbe863f3cb3642of222aa4f3aae6447')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'ac5db5814b262d8c8ca7c199a987af49')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Configuração do Dialogflow
DIALOGFLOW_PROJECT_ID = os.environ.get('DIALOGFLOW_PROJECT_ID', 'necuro-marketplace-bot')
DIALOGFLOW_LANGUAGE_CODE = 'pt-BR'  # Português do Brasil como padrão

# Dicionário para armazenar o estado da conversa de cada usuário
user_sessions = {}

def detect_intent_text(session_id, text, language_code=DIALOGFLOW_LANGUAGE_CODE):
    """
    Detecta a intenção do usuário usando o Dialogflow
    """
    try:
        session_client = dialogflow.SessionsClient()
        session = session_client.session_path(DIALOGFLOW_PROJECT_ID, session_id)
        
        text_input = dialogflow.types.TextInput(
            text=text, language_code=language_code)
        query_input = dialogflow.types.QueryInput(text=text_input)
        
        response = session_client.detect_intent(
            session=session, query_input=query_input)
        
        return response.query_result
    except Exception as e:
        logger.error(f"Erro ao detectar intenção: {e}")
        return None

def get_user_session(phone_number):
    """
    Obtém ou cria uma sessão para o usuário
    """
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'state': 'initial',
            'selected_category': None,
            'selected_establishment': None,
            'cart': [],
            'language': 'pt',  # Padrão para português
            'delivery_info': {}
        }
    return user_sessions[phone_number]

def handle_greeting(session):
    """
    Manipula a saudação inicial
    """
    response = "Olá! 👋 Bem-vindo(a) ao nosso marketplace! Como posso ajudar hoje? Procura algo específico ou gostaria de ver as nossas categorias?"
    if session['language'] == 'en':
        response = "Hello! 👋 Welcome to our marketplace! How can I help you today? Are you looking for something specific, or would you like to see our categories?"
    return response

def handle_show_categories(session):
    """
    Mostra as categorias disponíveis
    """
    categories = list(estabelecimentos_data.keys())
    
    if session['language'] == 'pt':
        response = "Temos uma variedade de opções para si! As nossas categorias principais são:\n\n"
        for i, category in enumerate(categories, 1):
            emoji = "🍔" if category == "pizzarias" or category == "restaurantes" else "🛍️" if category in ["brechos", "boutiques", "eletronicos", "ferragens"] else "🎵" if category == "discotecas" else "📦"
            response += f"{emoji} {i}. {category.capitalize()}\n"
        response += "\nEm qual delas está interessado(a)?"
    else:
        response = "We have a variety of options for you! Our main categories are:\n\n"
        for i, category in enumerate(categories, 1):
            emoji = "🍔" if category == "pizzarias" or category == "restaurantes" else "🛍️" if category in ["brechos", "boutiques", "eletronicos", "ferragens"] else "🎵" if category == "discotecas" else "📦"
            response += f"{emoji} {i}. {category.capitalize()}\n"
        response += "\nWhich one are you interested in?"
    
    session['state'] = 'selecting_category'
    return response

def handle_category_selection(session, message):
    """
    Manipula a seleção de categoria
    """
    categories = list(estabelecimentos_data.keys())
    selected_category = None
    
    # Tenta encontrar a categoria pelo nome
    for category in categories:
        if category.lower() in message.lower() or category[:-1].lower() in message.lower():
            selected_category = category
            break
    
    # Se não encontrou pelo nome, tenta pelo número
    if not selected_category:
        try:
            category_number = int(message.strip())
            if 1 <= category_number <= len(categories):
                selected_category = categories[category_number - 1]
        except ValueError:
            pass
    
    if not selected_category:
        if session['language'] == 'pt':
            return "Desculpe, não consegui identificar essa categoria. Por favor, escolha uma das categorias listadas ou digite o número correspondente."
        else:
            return "Sorry, I couldn't identify that category. Please choose one of the listed categories or type the corresponding number."
    
    session['selected_category'] = selected_category
    session['state'] = 'showing_establishments'
    
    establishments = estabelecimentos_data[selected_category]
    
    if session['language'] == 'pt':
        response = f"Ótimo! Aqui estão os estabelecimentos disponíveis na categoria {selected_category.capitalize()}:\n\n"
        for i, establishment in enumerate(establishments, 1):
            response += f"{i}. {establishment['nome']} - ⭐ {establishment['avaliacao_media']}\n"
        response += "\nQual deles gostaria de explorar?"
    else:
        response = f"Great! Here are the available establishments in the {selected_category.capitalize()} category:\n\n"
        for i, establishment in enumerate(establishments, 1):
            response += f"{i}. {establishment['nome']} - ⭐ {establishment['avaliacao_media']}\n"
        response += "\nWhich one would you like to explore?"
    
    return response

def handle_establishment_selection(session, message):
    """
    Manipula a seleção de estabelecimento
    """
    category = session['selected_category']
    establishments = estabelecimentos_data[category]
    selected_establishment = None
    
    # Tenta encontrar o estabelecimento pelo nome
    for establishment in establishments:
        if establishment['nome'].lower() in message.lower():
            selected_establishment = establishment
            break
    
    # Se não encontrou pelo nome, tenta pelo número
    if not selected_establishment:
        try:
            establishment_number = int(message.strip())
            if 1 <= establishment_number <= len(establishments):
                selected_establishment = establishments[establishment_number - 1]
        except ValueError:
            pass
    
    if not selected_establishment:
        if session['language'] == 'pt':
            return "Desculpe, não consegui identificar esse estabelecimento. Por favor, escolha um dos estabelecimentos listados ou digite o número correspondente."
        else:
            return "Sorry, I couldn't identify that establishment. Please choose one of the listed establishments or type the corresponding number."
    
    session['selected_establishment'] = selected_establishment
    session['state'] = 'showing_menu'
    
    # Verifica se o estabelecimento tem menu ou produtos
    items = []
    if 'menu' in selected_establishment:
        items = selected_establishment['menu']
    elif 'produtos' in selected_establishment:
        items = selected_establishment['produtos']
    
    if session['language'] == 'pt':
        response = f"Excelente escolha! Aqui está o menu/catálogo de {selected_establishment['nome']}:\n\n"
        for i, item in enumerate(items, 1):
            response += f"{i}. {item['nome']} - {item['preco']} MT\n   {item['descricao']}\n\n"
        
        response += f"\nLocalização: {selected_establishment['endereco']}\n"
        response += f"Horário de funcionamento: {selected_establishment['horario_funcionamento']}\n"
        response += f"Avaliação: ⭐ {selected_establishment['avaliacao_media']}\n\n"
        
        response += "O que gostaria de pedir?"
    else:
        response = f"Excellent choice! Here's the menu/catalog from {selected_establishment['nome']}:\n\n"
        for i, item in enumerate(items, 1):
            response += f"{i}. {item['nome']} - {item['preco']} MT\n   {item['descricao']}\n\n"
        
        response += f"\nLocation: {selected_establishment['endereco']}\n"
        response += f"Opening hours: {selected_establishment['horario_funcionamento']}\n"
        response += f"Rating: ⭐ {selected_establishment['avaliacao_media']}\n\n"
        
        response += "What would you like to order?"
    
    return response

def handle_item_selection(session, message):
    """
    Manipula a seleção de item do menu/catálogo
    """
    establishment = session['selected_establishment']
    
    # Verifica se o estabelecimento tem menu ou produtos
    items = []
    if 'menu' in establishment:
        items = establishment['menu']
    elif 'produtos' in establishment:
        items = establishment['produtos']
    
    selected_item = None
    
    # Tenta encontrar o item pelo nome
    for item in items:
        if item['nome'].lower() in message.lower():
            selected_item = item
            break
    
    # Se não encontrou pelo nome, tenta pelo número
    if not selected_item:
        try:
            item_number = int(message.strip())
            if 1 <= item_number <= len(items):
                selected_item = items[item_number - 1]
        except ValueError:
            pass
    
    if not selected_item:
        if session['language'] == 'pt':
            return "Desculpe, não consegui identificar esse item. Por favor, escolha um dos itens listados ou digite o número correspondente."
        else:
            return "Sorry, I couldn't identify that item. Please choose one of the listed items or type the corresponding number."
    
    session['selected_item'] = selected_item
    session['state'] = 'asking_quantity'
    
    if session['language'] == 'pt':
        return f"Ótima escolha! Quantos {selected_item['nome']} deseja?"
    else:
        return f"Great choice! How many {selected_item['nome']} would you like?"

def handle_quantity_selection(session, message):
    """
    Manipula a seleção de quantidade
    """
    try:
        # Tenta converter para número
        quantity = int(message.strip())
        if quantity <= 0:
            raise ValueError("Quantidade deve ser positiva")
    except ValueError:
        # Se não for um número, tenta interpretar palavras como "um", "dois", etc.
        quantity_words = {
            'um': 1, 'uma': 1, 'one': 1,
            'dois': 2, 'duas': 2, 'two': 2,
            'três': 3, 'tres': 3, 'three': 3,
            'quatro': 4, 'four': 4,
            'cinco': 5, 'five': 5
        }
        
        quantity = None
        for word, value in quantity_words.items():
            if word in message.lower():
                quantity = value
                break
        
        if quantity is None:
            if session['language'] == 'pt':
                return "Por favor, indique uma quantidade válida (um número ou palavras como 'um', 'dois', etc.)."
            else:
                return "Please provide a valid quantity (a number or words like 'one', 'two', etc.)."
    
    item = session['selected_item']
    
    # Adiciona ao carrinho
    cart_item = {
        'nome': item['nome'],
        'preco': item['preco'],
        'quantidade': quantity,
        'subtotal': item['preco'] * quantity
    }
    
    session['cart'].append(cart_item)
    session['state'] = 'asking_more_items'
    
    # Calcula o total do carrinho
    total = sum(item['subtotal'] for item in session['cart'])
    
    if session['language'] == 'pt':
        response = f"{quantity}x {item['nome']} adicionado(s) à sua sacola. ✅\n\n"
        response += "Sua sacola atual:\n"
        for cart_item in session['cart']:
            response += f"• {cart_item['quantidade']}x {cart_item['nome']} - {cart_item['subtotal']} MT\n"
        response += f"\nTotal parcial: {total} MT\n\n"
        response += "Vai querer mais alguma coisa?"
    else:
        response = f"{quantity}x {item['nome']} added to your bag. ✅\n\n"
        response += "Your current bag:\n"
        for cart_item in session['cart']:
            response += f"• {cart_item['quantidade']}x {cart_item['nome']} - {cart_item['subtotal']} MT\n"
        response += f"\nSubtotal: {total} MT\n\n"
        response += "Would you like anything else?"
    
    return response

def handle_more_items_response(session, message):
    """
    Manipula a resposta sobre querer mais itens
    """
    positive_responses = ['sim', 'yes', 'quero', 'want', 'mais', 'more']
    negative_responses = ['não', 'nao', 'no', 'pronto', 'finalizar', 'finish', 'done']
    
    # Verifica se é uma resposta positiva
    is_positive = any(word in message.lower() for word in positive_responses)
    
    # Verifica se é uma resposta negativa
    is_negative = any(word in message.lower() for word in negative_responses)
    
    if is_positive:
        # Se o usuário quer mais itens, volta para o menu
        session['state'] = 'showing_menu'
        establishment = session['selected_establishment']
        
        # Verifica se o estabelecimento tem menu ou produtos
        items = []
        if 'menu' in establishment:
            items = establishment['menu']
        elif 'produtos' in establishment:
            items = establishment['produtos']
        
        if session['language'] == 'pt':
            response = f"Claro! Aqui está novamente o menu/catálogo de {establishment['nome']}:\n\n"
            for i, item in enumerate(items, 1):
                response += f"{i}. {item['nome']} - {item['preco']} MT\n   {item['descricao']}\n\n"
            response += "O que mais gostaria de pedir?"
        else:
            response = f"Sure! Here's the menu/catalog from {establishment['nome']} again:\n\n"
            for i, item in enumerate(items, 1):
                response += f"{i}. {item['nome']} - {item['preco']} MT\n   {item['descricao']}\n\n"
            response += "What else would you like to order?"
        
        return response
    
    elif is_negative:
        # Se o usuário não quer mais itens, pergunta sobre entrega
        session['state'] = 'asking_delivery_method'
        
        if session['language'] == 'pt':
            return "Perfeito! Seu pedido está quase finalizado.\nPrefere receber por delivery (entrega) ou vir buscar no estabelecimento?"
        else:
            return "Perfect! Your order is almost complete.\nWould you prefer delivery or pickup at the establishment?"
    
    else:
        # Se a resposta não for clara
        if session['language'] == 'pt':
            return "Desculpe, não entendi. Você gostaria de pedir mais alguma coisa? Por favor, responda com 'sim' ou 'não'."
        else:
            return "Sorry, I didn't understand. Would you like to order anything else? Please answer with 'yes' or 'no'."

def handle_delivery_method(session, message):
    """
    Manipula a escolha do método de entrega
    """
    delivery_keywords = ['delivery', 'entrega', 'entregar', 'casa', 'home', 'deliver']
    pickup_keywords = ['buscar', 'pickup', 'retirar', 'retirada', 'loja', 'store', 'pick up']
    
    is_delivery = any(word in message.lower() for word in delivery_keywords)
    is_pickup = any(word in message.lower() for word in pickup_keywords)
    
    if is_delivery:
        session['delivery_method'] = 'delivery'
        session['state'] = 'asking_delivery_info'
        
        if session['language'] == 'pt':
            return "Entendido, entrega ao domicílio! Para calcularmos a taxa de entrega e agilizarmos o processo, por favor, informe:\n\n• O seu contacto para chamadas (se diferente do WhatsApp).\n• O seu bairro e um ponto de referência.\n• O horário em que gostaria de receber o pedido."
        else:
            return "Understood, home delivery! To calculate the delivery fee and speed up the process, please provide:\n\n• Your contact number for calls (if different from WhatsApp).\n• Your neighborhood and a reference point.\n• The time you would like to receive your order."
    
    elif is_pickup:
        session['delivery_method'] = 'pickup'
        session['state'] = 'asking_pickup_time'
        
        if session['language'] == 'pt':
            return "Ótimo, você optou por buscar no estabelecimento. A que horas pretende buscar o seu pedido?"
        else:
            return "Great, you've chosen to pick up at the establishment. What time do you plan to pick up your order?"
    
    else:
        if session['language'] == 'pt':
            return "Desculpe, não entendi sua escolha. Por favor, indique se prefere receber por delivery (entrega) ou se prefere buscar no estabelecimento."
        else:
            return "Sorry, I didn't understand your choice. Please indicate if you prefer delivery or pickup at the establishment."

def handle_delivery_info(session, message):
    """
    Manipula as informações de entrega
    """
    # Armazena as informações de entrega
    session['delivery_info'] = message
    session['state'] = 'showing_payment_methods'
    
    # Calcula uma taxa de entrega fictícia
    delivery_fee = 80  # MT
    
    # Calcula o total com a taxa de entrega
    subtotal = sum(item['subtotal'] for item in session['cart'])
    total = subtotal + delivery_fee
    
    if session['language'] == 'pt':
        response = "Obrigado pelas informações! A taxa de entrega para a sua localização é de 80 MT.\n\n"
        response += "Resumo do seu pedido:\n"
        for item in session['cart']:
            response += f"• {item['quantidade']}x {item['nome']} - {item['subtotal']} MT\n"
        response += f"Taxa de entrega - {delivery_fee} MT\n"
        response += f"\nTotal a pagar: {total} MT\n\n"
        response += "Estes são os nossos métodos de pagamento:\n\n"
        response += "1. E-Mola\n2. M-Pesa\n3. M-Kesh\n\n"
        response += "Qual prefere?"
    else:
        response = "Thank you for the information! The delivery fee to your location is 80 MT.\n\n"
        response += "Your order summary:\n"
        for item in session['cart']:
            response += f"• {item['quantidade']}x {item['nome']} - {item['subtotal']} MT\n"
        response += f"Delivery fee - {delivery_fee} MT\n"
        response += f"\nTotal to pay: {total} MT\n\n"
        response += "These are our payment methods:\n\n"
        response += "1. E-Mola\n2. M-Pesa\n3. M-Kesh\n\n"
        response += "Which do you prefer?"
    
    return response

def handle_pickup_time(session, message):
    """
    Manipula o horário de retirada
    """
    # Armazena o horário de retirada
    session['pickup_time'] = message
    session['state'] = 'showing_payment_methods'
    
    # Calcula o total (sem taxa de entrega)
    total = sum(item['subtotal'] for item in session['cart'])
    
    if session['language'] == 'pt':
        response = f"Perfeito! Seu pedido estará pronto para retirada às {message}.\n\n"
        response += "Resumo do seu pedido:\n"
        for item in session['cart']:
            response += f"• {item['quantidade']}x {item['nome']} - {item['subtotal']} MT\n"
        response += f"\nTotal a pagar: {total} MT\n\n"
        response += "Estes são os nossos métodos de pagamento:\n\n"
        response += "1. E-Mola\n2. M-Pesa\n3. M-Kesh\n\n"
        response += "Qual prefere?"
    else:
        response = f"Perfect! Your order will be ready for pickup at {message}.\n\n"
        response += "Your order summary:\n"
        for item in session['cart']:
            response += f"• {item['quantidade']}x {item['nome']} - {item['subtotal']} MT\n"
        response += f"\nTotal to pay: {total} MT\n\n"
        response += "These are our payment methods:\n\n"
        response += "1. E-Mola\n2. M-Pesa\n3. M-Kesh\n\n"
        response += "Which do you prefer?"
    
    return response

def handle_payment_method(session, message):
    """
    Manipula a escolha do método de pagamento
    """
    payment_methods = {
        '1': 'E-Mola',
        '2': 'M-Pesa',
        '3': 'M-Kesh',
        'e-mola': 'E-Mola',
        'm-pesa': 'M-Pesa',
        'm-kesh': 'M-Kesh',
        'emola': 'E-Mola',
        'mpesa': 'M-Pesa',
        'mkesh': 'M-Kesh'
    }
    
    selected_method = None
    for key, value in payment_methods.items():
        if key.lower() in message.lower():
            selected_method = value
            break
    
    if not selected_method:
        if session['language'] == 'pt':
            return "Desculpe, não reconheci esse método de pagamento. Por favor, escolha entre E-Mola, M-Pesa ou M-Kesh."
        else:
            return "Sorry, I didn't recognize that payment method. Please choose between E-Mola, M-Pesa, or M-Kesh."
    
    session['payment_method'] = selected_method
    session['state'] = 'showing_payment_details'
    
    payment_details = {
        'E-Mola': {
            'name': 'Necuro TI',
            'contact': '872321309'
        },
        'M-Pesa': {
            'name': 'Necuro TI',
            'contact': '841234567'
        },
        'M-Kesh': {
            'name': 'Necuro TI',
            'contact': '861234567'
        }
    }
    
    details = payment_details[selected_method]
    
    if session['language'] == 'pt':
        response = f"Escolheu {selected_method}. Estes são os dados para pagamento:\n\n"
        response += f"• Nome: {details['name']}\n"
        response += f"• Contacto: {details['contact']}\n\n"
        
        # Calcula o total
        if session['delivery_method'] == 'delivery':
            subtotal = sum(item['subtotal'] for item in session['cart'])
            total = subtotal + 80  # Taxa de entrega
        else:
            total = sum(item['subtotal'] for item in session['cart'])
        
        response += f"Assim que efetuar o pagamento de {total} MT, por favor, envie-nos o print do comprovativo aqui mesmo."
    else:
        response = f"You chose {selected_method}. Here are the payment details:\n\n"
        response += f"• Name: {details['name']}\n"
        response += f"• Contact: {details['contact']}\n\n"
        
        # Calcula o total
        if session['delivery_method'] == 'delivery':
            subtotal = sum(item['subtotal'] for item in session['cart'])
            total = subtotal + 80  # Taxa de entrega
        else:
            total = sum(item['subtotal'] for item in session['cart'])
        
        response += f"Once you've made the payment of {total} MT, please send us a screenshot of the receipt right here."
    
    return response

def handle_payment_proof(session, message):
    """
    Manipula o envio do comprovativo de pagamento
    """
    # Verifica se a mensagem contém uma imagem (comprovativo)
    has_image = 'MediaUrl' in message or 'NumMedia' in message and int(message['NumMedia']) > 0
    
    if has_image:
        session['state'] = 'order_completed'
        
        if session['language'] == 'pt':
            return "Comprovativo recebido! Muito obrigado. 😊\nUm dos nossos atendentes humanos irá verificar o pagamento e confirmar o seu pedido em breve. Por favor, aguarde a confirmação."
        else:
            return "Receipt received! Thank you very much. 😊\nOne of our human attendants will verify the payment and confirm your order soon. Please wait for confirmation."
    else:
        if session['language'] == 'pt':
            return "Por favor, envie uma imagem do comprovativo de pagamento para podermos processar o seu pedido."
        else:
            return "Please send an image of the payment receipt so we can process your order."

def process_message(phone_number, message_text, media_url=None):
    """
    Processa a mensagem recebida e retorna uma resposta
    """
    session = get_user_session(phone_number)
    
    # Verifica se é uma mensagem para mudar o idioma
    if message_text.lower() in ['english', 'inglês', 'ingles', 'en']:
        session['language'] = 'en'
        return "Language changed to English. How can I help you today?"
    elif message_text.lower() in ['português', 'portugues', 'portuguese', 'pt']:
        session['language'] = 'pt'
        return "Idioma alterado para Português. Como posso ajudar hoje?"
    
    # Verifica se é uma mensagem de ajuda
    if message_text.lower() in ['ajuda', 'help', 'socorro', 'sos']:
        if session['language'] == 'pt':
            return "Estou aqui para ajudar! Você pode dizer o que procura (ex: 'quero uma pizza', 'lojas de roupa'), pedir para ver as 'categorias', ou se estiver a meio de um pedido, pode dizer 'ver sacola' ou 'cancelar pedido'. Como posso assistir?"
        else:
            return "I'm here to help! You can tell me what you're looking for (e.g., 'I want a pizza', 'clothing stores'), ask to see the 'categories', or if you're in the middle of an order, you can say 'view bag' or 'cancel order'. How can I assist?"
    
    # Verifica se é uma mensagem para cancelar o pedido
    if message_text.lower() in ['cancelar', 'cancel', 'cancelar pedido', 'cancel order']:
        session['state'] = 'initial'
        session['selected_category'] = None
        session['selected_establishment'] = None
        session['cart'] = []
        
        if session['language'] == 'pt':
            return "Pedido cancelado. Como posso ajudar hoje?"
        else:
            return "Order canceled. How can I help you today?"
    
    # Verifica se é uma mensagem para ver o carrinho
    if message_text.lower() in ['ver sacola', 'view bag', 'carrinho', 'cart', 'sacola', 'bag']:
        if not session['cart']:
            if session['language'] == 'pt':
                return "Sua sacola está vazia. Como posso ajudar hoje?"
            else:
                return "Your bag is empty. How can I help you today?"
        
        total = sum(item['subtotal'] for item in session['cart'])
        
        if session['language'] == 'pt':
            response = "Sua sacola atual:\n"
            for item in session['cart']:
                response += f"• {item['quantidade']}x {item['nome']} - {item['subtotal']} MT\n"
            response += f"\nTotal parcial: {total} MT\n\n"
            response += "Deseja continuar com o pedido ou adicionar mais itens?"
        else:
            response = "Your current bag:\n"
            for item in session['cart']:
                response += f"• {item['quantidade']}x {item['nome']} - {item['subtotal']} MT\n"
            response += f"\nSubtotal: {total} MT\n\n"
            response += "Would you like to continue with the order or add more items?"
        
        return response
    
    # Processa a mensagem de acordo com o estado atual da conversa
    if session['state'] == 'initial':
        # Verifica se é uma saudação
        greetings = ['olá', 'ola', 'oi', 'hello', 'hi', 'hey', 'bom dia', 'boa tarde', 'boa noite']
        if any(greeting in message_text.lower() for greeting in greetings):
            return handle_greeting(session)
        
        # Verifica se está pedindo categorias
        category_requests = ['categorias', 'categories', 'opções', 'options', 'o que tem', 'what do you have']
        if any(request in message_text.lower() for request in category_requests):
            return handle_show_categories(session)
        
        # Se não for uma saudação ou pedido de categorias, tenta entender a intenção
        # Aqui seria ideal usar o Dialogflow, mas por enquanto vamos simplificar
        return handle_show_categories(session)
    
    elif session['state'] == 'selecting_category':
        return handle_category_selection(session, message_text)
    
    elif session['state'] == 'showing_establishments':
        return handle_establishment_selection(session, message_text)
    
    elif session['state'] == 'showing_menu':
        return handle_item_selection(session, message_text)
    
    elif session['state'] == 'asking_quantity':
        return handle_quantity_selection(session, message_text)
    
    elif session['state'] == 'asking_more_items':
        return handle_more_items_response(session, message_text)
    
    elif session['state'] == 'asking_delivery_method':
        return handle_delivery_method(session, message_text)
    
    elif session['state'] == 'asking_delivery_info':
        return handle_delivery_info(session, message_text)
    
    elif session['state'] == 'asking_pickup_time':
        return handle_pickup_time(session, message_text)
    
    elif session['state'] == 'showing_payment_methods':
        return handle_payment_method(session, message_text)
    
    elif session['state'] == 'showing_payment_details':
        # Se tiver uma imagem, considera como comprovativo
        if media_url:
            return handle_payment_proof(session, {'MediaUrl': media_url})
        else:
            # Se não tiver imagem, pede novamente
            if session['language'] == 'pt':
                return "Por favor, envie uma imagem do comprovativo de pagamento para podermos processar o seu pedido."
            else:
                return "Please send an image of the payment receipt so we can process your order."
    
    elif session['state'] == 'order_completed':
        # Se o pedido já foi completado, reinicia a conversa
        session['state'] = 'initial'
        session['selected_category'] = None
        session['selected_establishment'] = None
        session['cart'] = []
        
        if session['language'] == 'pt':
            return "Seu pedido anterior foi processado. Como posso ajudar hoje?"
        else:
            return "Your previous order has been processed. How can I help you today?"
    
    # Fallback para caso o estado não seja reconhecido
    session['state'] = 'initial'
    if session['language'] == 'pt':
        return "Desculpe, ocorreu um erro. Como posso ajudar hoje?"
    else:
        return "Sorry, an error occurred. How can I help you today?"

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Webhook para receber mensagens do Twilio
    """
    try:
        # Extrai informações da mensagem
        phone_number = request.values.get('From', '')
        message_text = request.values.get('Body', '')
        
        # Verifica se há mídia na mensagem
        num_media = int(request.values.get('NumMedia', 0))
        media_url = request.values.get('MediaUrl0', '') if num_media > 0 else None
        
        # Processa a mensagem
        response_text = process_message(phone_number, message_text, media_url)
        
        # Cria a resposta
        resp = MessagingResponse()
        resp.message(response_text)
        
        return str(resp)
    
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        resp = MessagingResponse()
        resp.message("Desculpe, ocorreu um erro. Por favor, tente novamente mais tarde.")
        return str(resp)

@app.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint para verificar a saúde da aplicação
    """
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    # Verifica se o arquivo de dados existe
    if not os.path.exists('dados_estabelecimentos.json'):
        logger.warning("Arquivo de dados não encontrado. Criando dados de exemplo...")
        # Copia o arquivo de dados do diretório raiz
        import shutil
        try:
            shutil.copy('/home/ubuntu/dados_estabelecimentos.json', 'dados_estabelecimentos.json')
            logger.info("Arquivo de dados copiado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao copiar arquivo de dados: {e}")
            # Cria um arquivo de dados mínimo
            with open('dados_estabelecimentos.json', 'w', encoding='utf-8') as f:
                json.dump({"pizzarias": []}, f)
    
    # Inicia o servidor Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
