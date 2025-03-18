import os
import logging
import sys
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import sqlite3
from sqlite3 import Error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, JobQueue, MessageHandler, filters, ConversationHandler
from telegram.error import InvalidToken
from pathlib import Path

# Load environment variables
load_dotenv()

# Admin user IDs loaded from environment variables
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '982793851').split(',')]

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_detailed.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_FILE = "tnetc_bot.db"

# Add constant for proof images path
PROOF_IMAGES_DIR = "/Users/hieuho/tnetPortal/proof_images"

# Add near the top with other constants
TESTIMONIAL_IMAGES_DIR = "/Users/hieuho/tnetPortal/testimonial_images"

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        return conn
    except Error as e:
        logger.error(f"Database connection error: {e}")
    
    return conn

def create_tables():
    """Create the necessary tables if they don't exist."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    join_date TEXT,
                    last_interaction TEXT,
                    purchased BOOLEAN DEFAULT 0,
                    campaign TEXT
                )
            ''')
            
            # Interactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    interaction_type TEXT,
                    interaction_data TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Services viewed table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS services_viewed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service TEXT,
                    view_count INTEGER DEFAULT 1,
                    last_viewed TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Purchases table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    plan_code TEXT,
                    purchase_date TEXT,
                    price TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Follow-ups table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS followups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service TEXT,
                    scheduled_date TEXT,
                    status TEXT DEFAULT 'scheduled',
                    response TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Testimonials table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS testimonials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    text TEXT,
                    image_path TEXT,
                    service TEXT,
                    timestamp TEXT,
                    active INTEGER DEFAULT 1
                )
            ''')
            
            conn.commit()
            logger.info("Database tables created successfully")
        except Error as e:
            logger.error(f"Database table creation error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def save_user(user_id, username, first_name, last_name, campaign=None):
    """Save or update user information in the database."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            
            current_time = datetime.now().isoformat()
            
            if user is None:
                # New user
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name, last_name, join_date, last_interaction, campaign) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, username, first_name, last_name, current_time, current_time, campaign)
                )
                logger.info(f"New user added to database: {user_id}")
            else:
                # Update existing user
                cursor.execute(
                    "UPDATE users SET username = ?, first_name = ?, last_name = ?, last_interaction = ? WHERE user_id = ?",
                    (username, first_name, last_name, current_time, user_id)
                )
                logger.info(f"User updated in database: {user_id}")
            
            conn.commit()
        except Error as e:
            logger.error(f"Database user save error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def log_interaction_to_db(user_id, interaction_type, interaction_data):
    """Log user interaction to the database."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Update last interaction time
            current_time = datetime.now().isoformat()
            cursor.execute(
                "UPDATE users SET last_interaction = ? WHERE user_id = ?",
                (current_time, user_id)
            )
            
            # Insert interaction record
            cursor.execute(
                "INSERT INTO interactions (user_id, interaction_type, interaction_data, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, interaction_type, json.dumps(interaction_data), current_time)
            )
            
            conn.commit()
        except Error as e:
            logger.error(f"Database interaction log error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def update_service_view(user_id, service):
    """Update the services viewed by the user."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            # Check if service view exists
            cursor.execute("SELECT * FROM services_viewed WHERE user_id = ? AND service = ?", (user_id, service))
            service_view = cursor.fetchone()
            
            if service_view is None:
                # New service view
                cursor.execute(
                    "INSERT INTO services_viewed (user_id, service, last_viewed) VALUES (?, ?, ?)",
                    (user_id, service, current_time)
                )
            else:
                # Update existing service view
                cursor.execute(
                    "UPDATE services_viewed SET view_count = view_count + 1, last_viewed = ? WHERE user_id = ? AND service = ?",
                    (current_time, user_id, service)
                )
            
            conn.commit()
        except Error as e:
            logger.error(f"Database service view update error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def record_purchase(user_id, plan_code, price):
    """Record a user purchase in the database."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            # Insert purchase record
            cursor.execute(
                "INSERT INTO purchases (user_id, plan_code, purchase_date, price) VALUES (?, ?, ?, ?)",
                (user_id, plan_code, current_time, price)
            )
            
            # Mark user as having purchased
            cursor.execute(
                "UPDATE users SET purchased = 1 WHERE user_id = ?",
                (user_id,)
            )
            
            conn.commit()
            logger.info(f"Purchase recorded for user {user_id}: {plan_code} at {price}")
        except Error as e:
            logger.error(f"Database purchase record error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def record_followup(user_id, service, scheduled_date):
    """Record a scheduled follow-up in the database."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Insert followup record
            cursor.execute(
                "INSERT INTO followups (user_id, service, scheduled_date) VALUES (?, ?, ?)",
                (user_id, service, scheduled_date)
            )
            
            conn.commit()
            logger.info(f"Follow-up scheduled for user {user_id} for {service} on {scheduled_date}")
        except Error as e:
            logger.error(f"Database followup record error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def update_followup_status(user_id, status, response=None):
    """Update the status of a follow-up."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            if response:
                cursor.execute(
                    "UPDATE followups SET status = ?, response = ? WHERE user_id = ? AND status = 'scheduled'",
                    (status, response, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE followups SET status = ? WHERE user_id = ? AND status = 'scheduled'",
                    (status, user_id)
                )
            
            conn.commit()
            logger.info(f"Follow-up status updated for user {user_id} to {status}")
        except Error as e:
            logger.error(f"Database followup status update error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")

def has_purchased(user_id):
    """Check if a user has made a purchase."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT purchased FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                return True
            return False
        except Error as e:
            logger.error(f"Database purchase check error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")
    
    return False

def add_testimonial(name, text, image_path, service):
    """Add a new testimonial to the database."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            cursor.execute(
                "INSERT INTO testimonials (name, text, image_path, service, timestamp) VALUES (?, ?, ?, ?, ?)",
                (name, text, image_path, service, current_time)
            )
            
            conn.commit()
            logger.info(f"New testimonial added for {name} on service {service}")
            return cursor.lastrowid
        except Error as e:
            logger.error(f"Database testimonial save error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")
    
    return None

def get_random_testimonials(service=None, limit=3):
    """Get random testimonials from image directory with generated content."""
    try:
        # Get all testimonial images
        image_files = [f for f in os.listdir(TESTIMONIAL_IMAGES_DIR) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        # Create testimonial entries
        testimonials = []
        for img_file in image_files:
            testimonials.append({
                'name': "Verified Member",
                'text': "This service changed my trading completely!",
                'image_path': os.path.join(TESTIMONIAL_IMAGES_DIR, img_file),
                'service': 'general'
            })
        
        # Randomize and limit results
        random.shuffle(testimonials)
        return testimonials[:limit]
        
    except Exception as e:
        logger.error(f"Error loading testimonial images: {str(e)}")
        return []

def get_all_testimonials():
    """Get all testimonials from the database."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM testimonials ORDER BY timestamp DESC")
            testimonials = cursor.fetchall()
            return testimonials
        except Error as e:
            logger.error(f"Database testimonial query error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")
    
    return []

def toggle_testimonial_status(testimonial_id, active=True):
    """Activate or deactivate a testimonial."""
    conn = create_connection()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE testimonials SET active = ? WHERE id = ?",
                (1 if active else 0, testimonial_id)
            )
            conn.commit()
            logger.info(f"Testimonial {testimonial_id} set to active={active}")
            return True
        except Error as e:
            logger.error(f"Database testimonial update error: {e}")
        finally:
            conn.close()
    else:
        logger.error("Cannot create database connection")
    
    return False

# Initialize database tables
create_tables()

# Dictionary to track user engagement (will be replaced by database)
user_engagement = {}

def log_user_interaction(update, interaction_type, data=None):
    """Log user interaction for analytics."""
    if update.effective_user:
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        
        # Save user to database
        save_user(user_id, username, first_name, last_name)
        
        # Log interaction to database
        if data:
            log_interaction_to_db(user_id, interaction_type, data)
        else:
            log_interaction_to_db(user_id, interaction_type, {})
        
        # For backward compatibility, also update the user_engagement dictionary
        if user_id not in user_engagement:
            user_engagement[user_id] = {
                'services_viewed': [],
                'last_interaction': datetime.now().isoformat(),
                'purchased': False
            }
        
        user_engagement[user_id]['last_interaction'] = datetime.now().isoformat()
        
        if interaction_type == 'service_view' and 'service' in data:
            service = data['service']
            if service not in user_engagement[user_id]['services_viewed']:
                user_engagement[user_id]['services_viewed'].append(service)
            
            # Update service view in database
            update_service_view(user_id, service)
        
        elif interaction_type == 'payment_confirmation':
            user_engagement[user_id]['purchased'] = True
            
            # Record purchase in database if plan info is available
            if 'plan' in data:
                plan_code = data['plan']
                price = "Unknown"
                
                if plan_code == 'monthly':
                    price = "$200"
                elif plan_code == 'quarterly':
                    price = "$500"
                elif plan_code == 'annual':
                    price = "$1500"
                elif plan_code == 'copytrade':
                    price = "$500"
                elif plan_code == 'standard_trial':
                    price = "Free Trial"
                elif plan_code == 'standard_monthly':
                    price = "$66/month"
                elif plan_code == 'standard_lifetime':
                    price = "$300"
                elif plan_code == 'vip_monthly':
                    price = "$300/month"
                elif plan_code == 'vip_lifetime':
                    price = "$2000"
                
                record_purchase(user_id, plan_code, price)

def validate_token():
    """Validate the bot token from environment variables."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("No token found! Make sure to create a .env file with your TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    if token == "your_bot_token_here":
        logger.error("Please replace the default token in .env with your actual bot token from BotFather")
        sys.exit(1)
    return token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    campaign = None
    
    # Check if there's a campaign parameter
    if context.args and len(context.args) > 0:
        campaign = context.args[0]
    
    # Save user to database with campaign info
    save_user(user.id, user.username, user.first_name, user.last_name, campaign)
    
    # Log start command
    log_user_interaction(update, "start_command", {"campaign": campaign})
    
    # Determine which welcome message to show based on campaign
    if campaign == 'ea_campaign':
        await ea_focused_welcome(update, context)
    elif campaign == 'signal_campaign':
        await signal_focused_welcome(update, context)
    elif campaign == 'vip_campaign':
        await vip_focused_welcome(update, context)
    else:
        await regular_welcome(update, context)

async def regular_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a detailed welcome message with all service options."""
    message = None
    chat_id = None
    
    if update.message:
        message = update.message
        chat_id = update.message.chat_id
        user = update.message.from_user
    elif update.callback_query:
        message = update.callback_query.message
        chat_id = update.callback_query.message.chat_id
        user = update.callback_query.from_user
    else:
        logger.error("Cannot identify message or user in regular_welcome")
        return
    
    # Log user interaction
    log_user_interaction(update, "welcome", {
        "source": "regular",
        "timestamp": datetime.now().isoformat()
    })
    
    # Save user if new
    user_first_name = user.first_name if hasattr(user, 'first_name') else ''
    user_last_name = user.last_name if hasattr(user, 'last_name') else ''
    username = user.username if hasattr(user, 'username') else ''
    
    save_user(chat_id, username, user_first_name, user_last_name)
    
    # Welcome message with FOMO elements
    welcome_text = (
        f"*🔥 Welcome to TNETC Trading's EXCLUSIVE Community! 🔥*\n\n"
        f"You've just discovered what the top 1% of traders DON'T want you to know. Our members are silently making consistent profits while others struggle.\n\n"
        f"*⚠️ LIMITED-TIME OPPORTUNITIES:*\n\n"
        f"*1. 🚀 X10 CHALLENGE - ALMOST SOLD OUT!*\n"
        f"• 10X your account in just 66 days (proven strategy)\n"
        f"• *ONLY 17 SLOTS LEFT* out of 100\n"
        f"• *$350 VALUE → $0 (FREE)* - Offer ends this week!\n\n"
        f"*2. 💰 LIFETIME COPYTRADE - NEVER OFFERED AGAIN*\n"
        f"• Automated profits without lifting a finger\n"
        f"• Members already making $500-$2500/week\n"
        f"• *$500 VALUE → $0 (FREE LIFETIME)* - Last chance!\n\n"
        f"*3. 💎 PREMIUM VIP SIGNAL + EA TRADING BOT*\n"
        f"• Our most elite package (94% win rate last month)\n"
        f"• Members reporting 40%+ monthly returns\n"
        f"• *ONLY 5 SPOTS* available at current pricing\n\n"
        f"*⏰ Which opportunity will you grab before it's gone?*"
    )
    
    # Create keyboard
    keyboard = [
        [InlineKeyboardButton("🔥 X10 Challenge (ONLY 17 SLOTS LEFT)", callback_data="special_challenge")],
        [InlineKeyboardButton("💰 Copytrade (FINAL FREE OFFER)", callback_data="copytrade_lifetime")],
        [InlineKeyboardButton("💎 Premium VIP Signal + EA Bot (5 SPOTS)", callback_data="premium_vip_ea")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Send welcome message
        if not message:
            await context.bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            try:
                await message.reply_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error replying to message: {str(e)}")
                # Fallback to sending new message
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=welcome_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        
        # 50% chance to send a testimonial after welcome
        if random.random() < 0.5:  # 50% chance
            # Schedule testimonial to be sent after 3-5 seconds
            delay = random.randint(3, 5)
            try:
                context.job_queue.run_once(
                    lambda ctx: send_testimonial_to_user(ctx, chat_id, 'general'),
                    delay,
                    name=f"welcome_testimonial_{chat_id}"
                )
                logger.info(f"Scheduled welcome testimonial for user {chat_id} with delay {delay}s")
            except Exception as e:
                logger.error(f"Error scheduling welcome testimonial: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error sending welcome message: {str(e)}")

async def ea_focused_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """EA-focused welcome for users coming from EA ads."""
    keyboard = [
        [InlineKeyboardButton("🚀 X10 CHALLENGE - 17 SLOTS LEFT!", callback_data='special_challenge')],
        [InlineKeyboardButton("💰 COPYTRADE - FINAL FREE OFFER", callback_data='copytrade_lifetime')],
        [InlineKeyboardButton("💎 PREMIUM VIP SIGNAL + EA BOT - 5 SPOTS", callback_data='premium_vip_ea')],
        [InlineKeyboardButton("📊 VIEW LIVE RESULTS - 94% WIN RATE", callback_data='ea_results')],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get chat ID safely
    chat_id = None
    if update.effective_chat:
        chat_id = update.effective_chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat_id
    
    if not chat_id:
        logger.error("Could not determine chat ID for EA focused welcome message")
        return
        
    message = (
        "*🔥 EXCLUSIVE ACCESS: TNETC PREMIUM TRADING SYSTEMS 🔥*\n\n"
        "You're among the select few to access our elite trading solutions that most traders will NEVER discover.\n\n"
        "*⚠️ TIME-SENSITIVE OPPORTUNITIES:*\n\n"
        "*🚀 X10 CHALLENGE - 83% SOLD OUT!*\n"
        "- Only 17 of 100 slots remaining\n"
        "- Our last challenge: 10X in JUST 66 days\n"
        "- Members reporting life-changing gains\n"
        "- *$350 VALUE - FREE ACCESS CLOSING THIS WEEK!*\n\n"
        "*💰 COPYTRADE SYSTEM - FINAL OFFER EVER*\n"
        "- Set & forget account growth (we trade for you)\n"
        "- Current members earning $500-$2500/week\n"
        "- Zero experience needed - 100% automated\n"
        "- *$500 VALUE - LIFETIME FREE ACCESS ENDING SOON*\n\n"
        "*💎 PREMIUM VIP + EA TRADING BOT - ALMOST FULL*\n"
        "- Our most powerful system (80% win rate)\n"
        "- Last month: FX +40.36% | GOLD +19.41%\n"
        "- Members consistently outperforming the market\n"
        "- *ONLY 5 SPOTS LEFT at current pricing!*\n\n"
        "*⏰ WHICH OPPORTUNITY WILL YOU CLAIM BEFORE IT'S GONE?*"
    )
    
    try:
        # Try to send message
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
            
        # 40% chance to send a testimonial after welcome
        if random.random() < 0.4:  # 40% chance
            # Schedule testimonial to be sent after 3-5 seconds
            delay = random.randint(3, 5)
            try:
                context.job_queue.run_once(
                    lambda ctx: send_testimonial_to_user(ctx, chat_id, 'ea'),
                    delay,
                    name=f"welcome_testimonial_{chat_id}"
                )
                logger.info(f"Scheduled EA focused welcome testimonial for user {chat_id}")
            except Exception as e:
                logger.error(f"Error scheduling EA welcome testimonial: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error sending EA focused welcome message: {str(e)}")
        # Try fallback
        try:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def signal_focused_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Signal-focused welcome for users coming from signal ads."""
    keyboard = [
        [InlineKeyboardButton("🚀 X10 CHALLENGE - 17 SLOTS LEFT!", callback_data='special_challenge')],
        [InlineKeyboardButton("💰 COPYTRADE - FINAL FREE OFFER", callback_data='copytrade_lifetime')],
        [InlineKeyboardButton("💎 PREMIUM VIP SIGNAL + EA BOT - 5 SPOTS", callback_data='premium_vip_ea')],
        [InlineKeyboardButton("📊 VIEW 94% WIN RATE PROOF", callback_data='signal_results')],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get chat ID safely
    chat_id = None
    if update.effective_chat:
        chat_id = update.effective_chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat_id
    
    if not chat_id:
        logger.error("Could not determine chat ID for Signal focused welcome message")
        return
        
    message = (
        "*🚨 URGENT: TNETC SIGNAL SERVICE - LIMITED ACCESS 🚨*\n\n"
        "You're viewing our ELITE signal service that most retail traders will never discover (94% win rate).\n\n"
        "*⚠️ ACT FAST - LIMITED OPPORTUNITIES:*\n\n"
        "*🚀 X10 CHALLENGE - NEARLY SOLD OUT!*\n"
        "- Only 17 slots remaining (83% already claimed)\n"
        "- Previous members: 10X gains in just 66 days\n"
        "- Proven strategy with verifiable results\n"
        "- *$350 VALUE - FREE ACCESS ENDS THIS WEEK!*\n\n"
        "*💰 COPYTRADE SYSTEM - LAST CHANCE EVER*\n"
        "- Hands-free profits (we trade for you)\n"
        "- Current members earning $500-$2500 weekly\n"
        "- 100% automated - no experience required\n"
        "- *$500 VALUE - LIFETIME FREE ACCESS CLOSING SOON*\n\n"
        "*💎 PREMIUM VIP SIGNAL + EA BOT - 5 SPOTS LEFT*\n"
        "- Our most powerful combo (highest returns)\n"
        "- Last month: +40.36% on FX, +19.41% on GOLD\n"
        "- Members consistently outperforming markets\n"
        "- *PRICE INCREASING NEXT WEEK - LAST CHANCE!*\n\n"
        "*⏰ DON'T MISS OUT - THESE OFFERS EXPIRE SOON!*"
    )
    
    try:
        # Try to send message
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
            
        # 40% chance to send a testimonial after welcome
        if random.random() < 0.4:  # 40% chance
            # Schedule testimonial to be sent after 3-5 seconds
            delay = random.randint(3, 5)
            try:
                context.job_queue.run_once(
                    lambda ctx: send_testimonial_to_user(ctx, chat_id, 'signal'),
                    delay,
                    name=f"welcome_testimonial_{chat_id}"
                )
                logger.info(f"Scheduled Signal focused welcome testimonial for user {chat_id}")
            except Exception as e:
                logger.error(f"Error scheduling Signal welcome testimonial: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error sending Signal focused welcome message: {str(e)}")
        # Try fallback
        try:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def vip_focused_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """VIP-focused welcome for users coming from VIP ads."""
    keyboard = [
        [InlineKeyboardButton("🚀 X10 CHALLENGE - 17 SLOTS LEFT!", callback_data='special_challenge')],
        [InlineKeyboardButton("💰 COPYTRADE - FINAL FREE OFFER", callback_data='copytrade_lifetime')],
        [InlineKeyboardButton("💎 PREMIUM VIP SIGNAL + EA BOT - 5 SPOTS", callback_data='premium_vip_ea')],
        [InlineKeyboardButton("🔒 EXCLUSIVE VIP BENEFITS", callback_data='vip_benefits')],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get chat ID safely
    chat_id = None
    if update.effective_chat:
        chat_id = update.effective_chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat_id
    
    if not chat_id:
        logger.error("Could not determine chat ID for VIP focused welcome message")
        return
        
    message = (
        "*💎 EXCLUSIVE: TNETC VIP INNER CIRCLE - BY INVITATION ONLY 💎*\n\n"
        "You've been granted access to our ELITE trading community that only the top 1% of traders ever discover.\n\n"
        "*⚠️ URGENT - FINAL ROUND OF OPPORTUNITIES:*\n\n"
        "*🚀 X10 CHALLENGE - 83% FILLED!*\n"
        "- Just 17 slots remain from original 100\n"
        "- Previous challenge: 10X return in 66 days\n"
        "- Members reporting life-changing profits\n"
        "- *$350 VALUE - FREE ACCESS ENDING THIS WEEK!*\n\n"
        "*💰 COPYTRADE SYSTEM - FINAL OPPORTUNITY*\n"
        "- Passive income without doing the work\n"
        "- Current members: $500-$2500 weekly profits\n"
        "- Zero learning curve - 100% automated\n"
        "- *$500 VALUE - NEVER FREE AGAIN AFTER THIS WEEK*\n\n"
        "*💎 PREMIUM VIP + EA TRADING BOT - 5 SPOTS REMAINING*\n"
        "- Our most elite package (highest ROI)\n"
        "- Proven: +40.36% FX & +19.41% GOLD last month\n"
        "- Exclusive strategies not shared publicly\n"
        "- *PRICE INCREASING 30% NEXT WEEK - LOCK IN NOW!*\n\n"
        "*⏰ WHICH ELITE OPPORTUNITY WILL YOU SECURE TODAY?*"
    )
    
    try:
        # Try to send message
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
            
        # 40% chance to send a testimonial after welcome
        if random.random() < 0.4:  # 40% chance
            # Schedule testimonial to be sent after 3-5 seconds
            delay = random.randint(3, 5)
            try:
                context.job_queue.run_once(
                    lambda ctx: send_testimonial_to_user(ctx, chat_id, 'vip'),
                    delay,
                    name=f"welcome_testimonial_{chat_id}"
                )
                logger.info(f"Scheduled VIP focused welcome testimonial for user {chat_id}")
            except Exception as e:
                logger.error(f"Error scheduling VIP welcome testimonial: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error sending VIP focused welcome message: {str(e)}")
        # Try fallback
        try:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def ea_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the EA-focused welcome message."""
    # For consistency with the new structure, just redirect to ea_focused_welcome
    await ea_focused_welcome(update, context)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboards."""
    query = update.callback_query
    
    try:
        await query.answer()
        data = query.data
        
        # Handle the different callback data
        log_user_interaction(update, "button_click", {
            "selection": data,
            "button_click_time": datetime.now().isoformat()
        })
        
        # Check if message is available (not too old)
        if query.message is None:
            logger.warning(f"Message is no longer available for callback {data}")
            # For navigation handlers, we need to handle the case where the message is None
            if data == 'show_all_services':
                await regular_welcome(update, context)
                return
            elif data == 'back_to_ea_welcome':
                await ea_focused_welcome(update, context)
                return
            elif data == 'back_to_signal_welcome':
                await signal_focused_welcome(update, context)
                return
            elif data == 'back_to_vip_welcome':
                await vip_focused_welcome(update, context)
                return
            elif data == 'back_to_ea_funnel':
                await ea_focused_welcome(update, context)
                return

        # Handle premium VIP with EA option
        if data == 'premium_vip_ea':
            await send_premium_vip_ea_details(update, context)
            # Schedule follow-up
            schedule_user_followup(update, context, 'vip_ea')
            
        # Handle specific plan selections
        elif data == 'special_challenge':
            keyboard = [
                [InlineKeyboardButton("🚀 CLAIM MY SPOT NOW (17 LEFT)", url="https://t.me/tnetccommunity/186")],
                [InlineKeyboardButton("📱 Contact Support", url='https://t.me/m/1Q0AzxOLNDY1')],
                [InlineKeyboardButton("⏱️ VIEW PREVIOUS CHALLENGE RESULTS", callback_data="ea_results")],
                [InlineKeyboardButton("« BACK TO ALL SERVICES", callback_data="show_all_services")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                if query.message:
                    await query.message.edit_text(
                        "*🔥 X10 CHALLENGE - FINAL 17 SPOTS AVAILABLE! 🔥*\n\n"
                        "*⚠️ WARNING: This offer is closing THIS WEEK ⚠️*\n\n"
                        "Our exclusive X10 Challenge has helped members achieve incredible results:\n\n"
                        "✅ Previous challenge: *10X account growth in just 66 days*\n"
                        "✅ Members reporting $500-$3,000+ profits weekly\n"
                        "✅ Step-by-step guidance from professional traders\n"
                        "✅ Proven strategy with 94% win rate\n\n"
                        "*WHAT YOU GET:*\n"
                        "• Access to exclusive challenge group\n"
                        "• Premium signals (not available elsewhere)\n"
                        "• 1-on-1 strategy coaching\n"
                        "• Daily trade opportunities\n\n"
                        "*ORIGINAL PRICE: $350*\n"
                        "*CURRENT PRICE: $0 (FREE)*\n\n"
                        "*⏰ ONLY 17 SPOTS REMAIN - OFFER ENDS THIS WEEK!*\n"
                        "Our last batch of members filled within 24 hours. Don't miss this opportunity!",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    # Fallback if message is too old
                    chat_id = update.effective_chat.id
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="*🔥 X10 CHALLENGE - FINAL 17 SPOTS AVAILABLE! 🔥*\n\n"
                        "*⚠️ WARNING: This offer is closing THIS WEEK ⚠️*\n\n"
                        "Our exclusive X10 Challenge has helped members achieve incredible results:\n\n"
                        "✅ Previous challenge: *10X account growth in just 66 days*\n"
                        "✅ Members reporting $500-$3,000+ profits weekly\n"
                        "✅ Step-by-step guidance from professional traders\n"
                        "✅ Proven strategy with 94% win rate\n\n"
                        "*WHAT YOU GET:*\n"
                        "• Access to exclusive challenge group\n"
                        "• Premium signals (not available elsewhere)\n"
                        "• 1-on-1 strategy coaching\n"
                        "• Daily trade opportunities\n\n"
                        "*ORIGINAL PRICE: $350*\n"
                        "*CURRENT PRICE: $0 (FREE)*\n\n"
                        "*⏰ ONLY 17 SPOTS REMAIN - OFFER ENDS THIS WEEK!*\n"
                        "Our last batch of members filled within 24 hours. Don't miss this opportunity!",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                
                # Schedule follow-up
                schedule_user_followup(update, context, 'challenge')
                
            except Exception as e:
                logger.error(f"Error sending special challenge info: {str(e)}")
                # Try fallback message
                try:
                    chat_id = update.effective_chat.id
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="*🔥 X10 CHALLENGE - FINAL 17 SPOTS AVAILABLE! 🔥*\n\n"
                        "*Sorry, we couldn't update the message. Please click the button again or contact support if this persists.*",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                except Exception as inner_e:
                    logger.error(f"Fallback message also failed: {str(inner_e)}")
                    
        elif data == 'copytrade_lifetime':
            # Special handling for copytrade lifetime plan
            keyboard = [
                [InlineKeyboardButton("📱 Contact Support", url='https://t.me/m/KAYFGGyMYzk1')],
                [InlineKeyboardButton("📊 View Profit Proof", callback_data='copytrade_profit_proof')],
                [InlineKeyboardButton("🔙 Back to Plans", callback_data='show_all_services')]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                "*🔥 TNETC Copytrade Plan - FREE! 🔥*\n\n"
                "Our Copytrade Plan is perfect for those who want to earn from trading without having to trade themselves.\n\n"
                "*What's Included:*\n"
                "✅ Copy trade us on Puprime - we handle everything\n"
                "✅ 1-on-1 account setup support\n"
                "✅ Weekly performance reports\n"
                "✅ Perfect for beginners - no trading knowledge needed\n\n"
                "*Limited Time Offer:*\n"
                "• Regular Price: $500 (lifetime access)\n"
                "• Current Promotion: FREE!\n\n"
                "To get started with our Copytrade Plan, contact our support team using the button below."
            )
            
            try:
                if query.message:
                    await query.message.reply_text(
                        message,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    # Fallback if message is None
                    chat_id = update.effective_chat.id
                    await query.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Error sending copytrade info: {str(e)}")
                
            # Schedule follow-up
            schedule_user_followup(update, context, 'copytrade')

        elif data == 'standard_trial':
            await send_plan_details(
                update, 
                "⭐️ Standard Plan - 1 Week FREE Trial",
                "Try our Standard Plan free for one week!",
                "Standard Trial",
                "7 DAY FREE TRIAL"
            )
            # Schedule follow-up
            schedule_user_followup(update, context, 'standard')
            
        elif data == 'standard_monthly':
            await send_plan_details(
                update, 
                "⭐️ Standard Plan - $66/month",
                "Monthly subscription to our Standard Plan.",
                "Standard Monthly",
                "$66/month"
            )
            # Schedule follow-up
            schedule_user_followup(update, context, 'standard')
            
        elif data == 'standard_lifetime':
            await send_plan_details(
                update, 
                "⭐️ Standard Plan - $300/lifetime",
                "Lifetime access to our Standard Plan.",
                "Standard Lifetime",
                "$300 one-time"
            )
            # Schedule follow-up
            schedule_user_followup(update, context, 'standard')
            
        elif data == 'vip_monthly':
            await send_plan_details(
                update, 
                "⭐️ VIP Plan - $300/month",
                "Monthly subscription to our premium VIP Plan.",
                "VIP Monthly",
                "$300/month"
            )
            # Schedule follow-up
            schedule_user_followup(update, context, 'vip')
            
        elif data == 'vip_lifetime':
            await send_plan_details(
                update, 
                "⭐️ VIP Plan - $2000/lifetime",
                "Lifetime access to our premium VIP Plan.",
                "VIP Lifetime",
                "$2000 one-time"
            )
            # Schedule follow-up
            schedule_user_followup(update, context, 'vip')
            
        # EA-specific handlers
        elif data == 'ea_results':
            await send_ea_results(update, context)
            
        elif data == 'ea_stats':
            await send_ea_performance(update, context)
            
        elif data == 'ea_how_works':
            await send_ea_explanation(update, context)
            
        elif data == 'ea_pricing':
            await send_ea_pricing(update, context)
            
        # Signal-specific handlers
        elif data == 'signal_results':
            await send_signal_results(update, context)
            
        # VIP-specific handlers
        elif data == 'vip_benefits':
            await send_vip_benefits(update, context)
            
        # Navigation handlers
        elif data == 'show_all_services':
            try:
                if query.message:
                    await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {str(e)}")
            await regular_welcome(update, context)
        elif data == 'back_to_ea_welcome':
            try:
                if query.message:
                    await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {str(e)}")
            await ea_focused_welcome(update, context)
        elif data == 'back_to_signal_welcome':
            try:
                if query.message:
                    await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {str(e)}")
            await signal_focused_welcome(update, context)
        elif data == 'back_to_vip_welcome':
            try:
                if query.message:
                    await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {str(e)}")
            await vip_focused_welcome(update, context)
            await ea_focused_welcome(update, context)
            
        # EA purchase handlers
        elif data.startswith('purchase_'):
            await handle_purchase_selection(update, context)
            
        # Payment confirmation handlers
        elif data.startswith('payment_made_'):
            await handle_payment_confirmation(update, context)
            
        # Setup guide handlers
        elif data.startswith('setup_guide_'):
            await send_setup_guide(update, context)
            
        # Follow-up response handlers
        elif data.startswith('resume_') or data.startswith('followup_'):
            await handle_followup_response(update, context)
            
        # After handling standard button options, randomly send a testimonial (20% chance)
        if random.random() < 0.2:  # 20% chance
            service = None
            
            # Try to determine relevant service from the button clicked
            if "ea" in data:
                service = "ea"
            elif "vip" in data:
                service = "vip"
            elif "signal" in data:
                service = "signal"
            elif "copytrade" in data:
                service = "copytrade"
            elif "challenge" in data:
                service = "challenge"
            
            # Schedule testimonial to be sent 3-5 seconds after the response
            delay = random.randint(3, 5)
            context.job_queue.run_once(
                lambda ctx: send_testimonial_to_user(ctx, query.message.chat_id, service),
                delay,
                name=f"testimonial_{query.message.chat_id}"
            )
            
            logger.info(f"Scheduled testimonial for user {query.message.chat_id} with delay {delay}s")
        
    except Exception as e:
        logger.error(f"Error handling button click: {str(e)}")
        try:
            await query.edit_message_text(
                "Sorry, there was an error processing your request. Please try again or type /start to restart."
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message: {str(inner_e)}")

async def send_plan_details(update, title, description, plan_code, price):
    """Send details about a plan."""
    # Check if message is available
    if update.callback_query and update.callback_query.message is None:
        logger.warning(f"Message no longer available for plan_details: {plan_code}")
        try:
            # Fallback to sending a new message
            chat_id = update.effective_chat.id
            text = create_plan_text(title, description, plan_code, price)
            reply_markup = create_plan_keyboard(plan_code)
            
            await update.callback_query.bot.send_message(
                chat_id=chat_id, 
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return True
        except Exception as e:
            logger.error(f"Error sending plan details fallback: {str(e)}")
            return False
    
    text = create_plan_text(title, description, plan_code, price)
    reply_markup = create_plan_keyboard(plan_code)
    
    try:
        if update.callback_query and update.callback_query.message:
            message = update.callback_query.message
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
            
            # 30% chance to send a testimonial after plan details
            if random.random() < 0.3:  # 30% chance
                # Send testimonial related to this plan
                service = None
                if "ea" in plan_code:
                    service = "ea"
                elif "vip" in plan_code:
                    service = "vip"
                elif "signal" in plan_code:
                    service = "signal"
                elif "copytrade" in plan_code:
                    service = "copytrade"
                elif "challenge" in plan_code:
                    service = "challenge"
                
                # Schedule testimonial to be sent 2-4 seconds after the plan details
                delay = random.randint(2, 4)
                context = update.callback_query._context
                if context and hasattr(context, 'job_queue') and context.job_queue:
                    context.job_queue.run_once(
                        lambda ctx: send_testimonial_to_user(ctx, message.chat_id, service),
                        delay,
                        name=f"testimonial_{message.chat_id}"
                    )
                    logger.info(f"Scheduled testimonial for user {message.chat_id} with delay {delay}s")
            
            logger.info(f"Plan details sent for {plan_code}")
            return True
        else:
            logger.error("No message available to update")
            return False
    except Exception as e:
        logger.error(f"Error sending plan details: {str(e)}")
        try:
            # Fallback to sending a new message
            chat_id = update.effective_chat.id
            await update.callback_query.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return True
        except Exception as inner_e:
            logger.error(f"Error sending plan details fallback: {str(inner_e)}")
            return False

def create_plan_text(title, description, plan_code, price):
    """Create formatted text for a plan."""
    return (
        f"*{title}*\n\n"
        f"{description}\n\n"
        f"*Price: {price}*\n\n"
        f"To purchase this plan, click the button below."
    )

def create_plan_keyboard(plan_code):
    """Create keyboard with purchase button for a plan."""
    keyboard = [
        [InlineKeyboardButton("Purchase Now", callback_data=f"purchase_{plan_code}")],
        [InlineKeyboardButton("« Back to all services", callback_data="show_all_services")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_ea_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send EA performance results."""
    keyboard = [
        [InlineKeyboardButton("💎 Premium VIP Signal + EA Bundle", callback_data='premium_vip_ea')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_to_ea_welcome')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        "📊 *TNETC TRADING PERFORMANCE RESULTS* 📊\n\n"
        "*Monthly Performance (Last 3 Months):*\n"
        "• April: +25.3%\n"
        "• May: +52.3%\n"
        "• June: +40.36%\n\n"
        "*Performance by Market:*\n"
        "• Forex: +40.36% ✅\n"
        "• Gold: +19.41% ✅\n\n"
        "*Key Performance Metrics:*\n"
        "• Win Rate: 80% for EA, 94% for Signals\n"
        "• Profit Factor: 3.2\n"
        "• Average Win/Loss Ratio: 3.5\n"
        "• Maximum Drawdown: 8.3%\n\n"
        "Get these results with our Premium VIP Signal + EA Trading Bot package or take advantage of our FREE x10 Challenge or Copytrade offers!"
    )

    try:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif update.message:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Fallback if both are None
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error sending EA results: {str(e)}")
        # Try one more fallback
        try:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def schedule_followup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule a follow-up message for users who showed interest but didn't purchase."""
    job = context.job
    data = job.data
    
    user_id = data.get('user_id')
    service = data.get('service')
    
    # Check if user has purchased using database
    if has_purchased(user_id):
        logger.info(f"User {user_id} has already purchased, skipping follow-up")
        return
    
    # Get chat ID
    chat_id = user_id
    
    # Determine which service the user was interested in
    service_messages = {
        'ea': "I noticed you were exploring our EA Trading Bot recently. Our automated system has a proven 80% win rate and has helped many traders achieve consistent profits.",
        'vip': "I noticed you were checking out our VIP Trading Plan. Our VIP members enjoy exclusive benefits like 1-on-1 signal guidance and higher returns.",
        'signal': "I noticed you were looking at our Signal Service. Our signals have a 94% win rate and can significantly improve your trading results.",
        'standard': "I noticed you were exploring our Standard Plan. It's a great way to get started with our premium trading signals and support.",
        'copytrade': "I noticed you were checking out our Copytrade Plan. It's perfect if you want to earn without having to trade yourself - we handle everything for you.",
        'challenge': "I noticed you were exploring our x10 Challenge. This exclusive opportunity has helped traders multiply their accounts by 10x in just 66 days.",
        'vip_ea': "I noticed you were exploring our Premium VIP Signal + EA Trading Bot package. This comprehensive solution gives you the best of both worlds."
    }
    
    base_message = service_messages.get(service, "I noticed you were exploring our services recently but didn't complete your purchase.")
    
    # Create follow-up message with options
    message = (
        f"👋 *Follow-up from TNETC Trading*\n\n"
        f"{base_message}\n\n"
        f"Check out what our customers are saying:"
    )
    
    keyboard = [
        [InlineKeyboardButton("Continue Where I Left Off", callback_data=f'resume_{service}')],
        [InlineKeyboardButton("I Have Questions", callback_data='followup_questions')],
        [InlineKeyboardButton("Not Interested", callback_data='followup_not_interested')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Send initial message
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Send testimonial images from directory
        try:
            testimonials = get_random_testimonials(service, 2)
            
            for testimonial in testimonials:
                img_path = testimonial['image_path']
                if os.path.exists(img_path):
                    caption = f"*{testimonial['name']}:* {testimonial['text']}"
                    with open(img_path, 'rb') as photo:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=caption,
                            parse_mode='Markdown'
                        )
        
        except Exception as e:
            logger.error(f"Error sending follow-up testimonials: {str(e)}")
        
        logger.info(f"Follow-up message sent to user {user_id} for {service}")
        
        # Update follow-up status in database
        update_followup_status(user_id, "sent")
    except Exception as e:
        logger.error(f"Error sending follow-up message: {str(e)}")
        
        # Update follow-up status in database
        update_followup_status(user_id, "failed")

def schedule_user_followup(update: Update, context: ContextTypes.DEFAULT_TYPE, service: str) -> None:
    """Schedule a follow-up for a user who viewed a service but didn't purchase."""
    user_id = update.effective_user.id
    
    # Don't schedule if user has already purchased
    if has_purchased(user_id):
        return
    
    # Check if job_queue is available
    if not context.job_queue:
        logger.error(f"Job queue is not available for user {user_id}, cannot schedule follow-up")
        return
    
    # Calculate scheduled date (24 hours later)
    scheduled_date = (datetime.now() + timedelta(hours=24)).isoformat()
    
    # Record follow-up in database
    record_followup(user_id, service, scheduled_date)
    
    # Schedule follow-up for 24 hours later
    context.job_queue.run_once(
        lambda ctx: send_testimonial_to_user(ctx, chat_id, service),
        timedelta(hours=24),
        name=f"followup_{user_id}_{service}"
    )
    
    logger.info(f"Scheduled follow-up for user {user_id} for {service} in 24 hours")

async def handle_purchase_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when a user selects a plan to purchase."""
    query = update.callback_query
    await query.answer()

    plan = query.data.replace('purchase_', '')
    
    # Log purchase intent
    log_user_interaction(update, "purchase_intent", {"plan": plan})
    
    # Get plan details
    plan_details = {
        'monthly': {'name': 'Monthly EA Plan', 'price': '$200', 'service': 'ea'},
        'quarterly': {'name': 'Quarterly EA Plan', 'price': '$500', 'service': 'ea'},
        'annual': {'name': 'Annual EA Plan', 'price': '$1500', 'service': 'ea'},
        'copytrade': {'name': 'Copytrade Lifetime Plan', 'price': '$500', 'service': 'copytrade'}
    }
    
    plan_name = plan_details.get(plan, {}).get('name', f"{plan.capitalize()} Plan")
    plan_price = plan_details.get(plan, {}).get('price', 'Custom Price')
    service = plan_details.get(plan, {}).get('service', 'ea')
    
    # Payment instructions
    keyboard = [
        [InlineKeyboardButton("📱 Contact Support", url='https://t.me/m/DvGbHx0NZTFl')],
        [InlineKeyboardButton("✅ I've Made Payment", callback_data=f'payment_made_{plan}')],
        [InlineKeyboardButton("🔙 Back to Plans", callback_data='ea_pricing')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        f"*How to Complete Your {plan_name} Purchase*\n\n"
        f"*Price: {plan_price}*\n\n"
        f"1. Contact our support team with code: `EA_{plan.upper()}_{query.from_user.id}`\n"
        f"2. Our team will provide payment instructions\n"
        f"3. After payment, you'll receive your EA setup within 24 hours\n\n"
        f"Questions? Our support team is available 24/7."
    )
    
    try:
        if query.message:
            await query.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Fallback if message is None
            chat_id = update.effective_chat.id
            await query.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        # Schedule a follow-up if user doesn't complete purchase
        schedule_user_followup(update, context, service)
        
        # Always send a related testimonial after purchase selection
        if message:
            chat_id = message.chat.id
            # Determine which service was selected
            service = None
            if "ea" in plan_code:
                service = "ea"
            elif "vip" in plan_code:
                service = "vip"
            elif "signal" in plan_code:
                service = "signal"
            elif "copytrade" in plan_code:
                service = "copytrade"
            elif "challenge" in plan_code:
                service = "challenge"
            
            # Schedule testimonial to be sent 3 seconds after the purchase options
            context.job_queue.run_once(
                lambda ctx: send_testimonial_to_user(ctx, chat_id, service),
                3,  # 3 seconds delay
                name=f"testimonial_{chat_id}"
            )
            
            logger.info(f"Scheduled purchase testimonial for user {chat_id}")
        
    except Exception as e:
        logger.error(f"Error sending purchase selection info: {str(e)}")

async def handle_payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle payment confirmation."""
    query = update.callback_query
    await query.answer()
    
    plan = query.data.replace('payment_made_', '')
    
    # Log payment confirmation
    log_user_interaction(update, "payment_confirmation", {"plan": plan})
    
    # Mark user as having purchased to prevent follow-ups
    user_id = update.effective_user.id
    
    # Record purchase in database
    price = "Unknown"
    if plan == 'monthly':
        price = "$200"
    elif plan == 'quarterly':
        price = "$500"
    elif plan == 'annual':
        price = "$1500"
    elif plan == 'copytrade':
        price = "$500"
    elif plan == 'standard_trial':
        price = "Free Trial"
    elif plan == 'standard_monthly':
        price = "$66/month"
    elif plan == 'standard_lifetime':
        price = "$300"
    elif plan == 'vip_monthly':
        price = "$300/month"
    elif plan == 'vip_lifetime':
        price = "$2000"
    
    record_purchase(user_id, plan, price)
    
    # Update follow-up status in database
    update_followup_status(user_id, "canceled", "user_purchased")
    
    # Cancel any scheduled follow-ups for this user
    if context.job_queue:
        current_jobs = context.job_queue.get_jobs_by_name(f"followup_{user_id}")
        for job in current_jobs:
            job.schedule_removal()
    else:
        logger.warning(f"Job queue is not available for user {user_id}, cannot cancel follow-ups")
    
    # Get plan details
    plan_details = {
        'monthly': {'name': 'Monthly EA Plan'},
        'quarterly': {'name': 'Quarterly EA Plan'},
        'annual': {'name': 'Annual EA Plan'},
        'copytrade': {'name': 'Copytrade Lifetime Plan'},
        'standard_trial': {'name': 'Standard Trial Plan'},
        'standard_monthly': {'name': 'Standard Monthly Plan'},
        'standard_lifetime': {'name': 'Standard Lifetime Plan'},
        'vip_monthly': {'name': 'VIP Monthly Plan'},
        'vip_lifetime': {'name': 'VIP Lifetime Plan'}
    }
    
    plan_name = plan_details.get(plan, {}).get('name', f"{plan.capitalize()} Plan")
    
    # Onboarding instructions
    keyboard = [
        [InlineKeyboardButton("📱 Contact Support", url='https://t.me/trump_tnetc_admin')],
        [InlineKeyboardButton("📚 Setup Guide", callback_data=f'setup_guide_{plan}')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='show_all_services')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        f"*Thank You for Your {plan_name} Purchase!*\n\n"
        f"Your payment confirmation has been received and our team has been notified.\n\n"
        f"*Next Steps:*\n"
        f"1. Our support team will contact you within 24 hours\n"
        f"2. They will guide you through the setup process\n"
        f"3. You'll receive access to your EA and all included benefits\n\n"
        f"Need immediate assistance? Contact our support team directly."
    )
    
    try:
        if query.message:
            await query.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Fallback if message is None
            chat_id = update.effective_chat.id
            await query.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error sending payment confirmation: {str(e)}")

async def handle_followup_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle responses to follow-up messages."""
    query = update.callback_query
    await query.answer()
    
    response = query.data
    user_id = update.effective_user.id
    
    # Log the follow-up response
    log_user_interaction(update, "followup_response", {"response": response})
    
    if response.startswith('resume_'):
        # User wants to resume where they left off
        service = response.replace('resume_', '')
        
        # Update follow-up status in database
        update_followup_status(user_id, "responded", "resume_service")
        
        # Direct to appropriate service page
        if service == 'ea':
            await ea_focused_welcome(update, context)
        elif service == 'vip':
            await vip_focused_welcome(update, context)
        elif service == 'signal':
            await signal_focused_welcome(update, context)
        elif service == 'copytrade':
            # For copytrade, show the copytrade plan details
            await send_plan_details(
                update, 
                "⭐️ Copytrade Plan - $500/lifetime",
                "Lifetime access to our Copytrade Plan.",
                "Copytrade Lifetime",
                "$500 one-time"
            )
        else:
            # Default to regular welcome
            await regular_welcome(update, context)
            
    elif response == 'followup_questions':
        # User has questions
        # Update follow-up status in database
        update_followup_status(user_id, "responded", "has_questions")
        
        keyboard = [
            [InlineKeyboardButton("📱 Contact Support", url='https://t.me/trump_tnetc_admin')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='show_all_services')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            "*We're Here to Help!*\n\n"
            "Our support team is ready to answer any questions you might have about our services.\n\n"
            "Common questions:\n"
            "• How does the EA trading bot work?\n"
            "• What's the difference between Standard and VIP plans?\n"
            "• How do I set up copy trading?\n"
            "• What's the refund policy?\n\n"
            "Click the button below to chat with our support team directly."
        )
        
        try:
            if query.message:
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                # Fallback if message is None
                chat_id = update.effective_chat.id
                await query.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error sending followup questions response: {str(e)}")
        
    elif response == 'followup_not_interested':
        # User is not interested
        # Update follow-up status in database
        update_followup_status(user_id, "responded", "not_interested")
        
        message = (
            "Thank you for letting us know. We appreciate your time!\n\n"
            "If you change your mind or have questions in the future, feel free to reach out to us anytime.\n\n"
            "Wishing you success in your trading journey! 🚀"
        )
        
        try:
            if query.message:
                await query.message.reply_text(message)
            else:
                # Fallback if message is None
                chat_id = update.effective_chat.id
                await query.bot.send_message(
                    chat_id=chat_id,
                    text=message
                )
        except Exception as e:
            logger.error(f"Error sending followup not interested response: {str(e)}")

async def send_setup_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send EA setup guide."""
    query = update.callback_query
    await query.answer()
    
    plan = query.data.replace('setup_guide_', '')
    
    # Log setup guide request
    log_user_interaction(update, "setup_guide_request", {"plan": plan})
    
    # Different guides based on plan
    if plan == 'copytrade':
        guide_text = (
            "*TNETC Copytrade Setup Guide*\n\n"
            "*Step 1: Create Puprime Account*\n"
            "• Register at Puprime using our referral link\n"
            "• Complete verification process\n"
            "• Fund your account (minimum $500 recommended)\n\n"
            "*Step 2: Share Account Details*\n"
            "• Provide your Puprime account number to our support team\n"
            "• Share your read-only password for monitoring\n"
            "• Set account leverage (1:100 recommended)\n\n"
            "*Step 3: Confirm Settings*\n"
            "• Confirm risk parameters with our team\n"
            "• Set account leverage (1:100 recommended)\n\n"
            "*Step 4: Start Earning*\n"
            "• Our team will handle all trading\n"
            "• You'll receive weekly performance reports\n"
            "• Monitor your account anytime through Puprime\n\n"
            "Need help? Our support team is available 24/7."
        )
    else:
        guide_text = (
            "*TNETC EA Setup Guide*\n\n"
            "*Step 1: Prepare Your Trading Account*\n"
            "• Ensure you have MT4/MT5 installed\n"
            "• Create/use a funded account (minimum $1000 recommended)\n"
            "• Set account leverage (1:100 or higher recommended)\n\n"
            "*Step 2: Install the EA*\n"
            "• Our team will provide the EA file\n"
            "• Follow our installation instructions\n"
            "• Place EA on correct currency pairs\n\n"
            "*Step 3: Configure Settings*\n"
            "• Set risk per trade (1% recommended)\n"
            "• Configure trading sessions\n"
            "• Set maximum open trades\n\n"
            "*Step 4: Monitoring & Support*\n"
            "• Regular performance reviews\n"
            "• 24/7 technical support\n"
            "• Strategy updates as market conditions change\n\n"
            "Need help? Our support team is available 24/7."
        )
    
    keyboard = [
        [InlineKeyboardButton("📱 Contact Support", url='https://t.me/trump_tnetc_admin')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='show_all_services')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if query.message:
            await query.message.reply_text(
                guide_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Fallback if message is None
            chat_id = update.effective_chat.id
            await query.bot.send_message(
                chat_id=chat_id,
                text=guide_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error sending setup guide: {str(e)}")

async def send_ea_performance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send detailed EA performance statistics."""
    # Check if message is available
    if update.callback_query.message is None:
        logger.warning("Message is no longer available for EA performance stats")
        return
        
    message = (
        "📊 *TNETC EA DETAILED PERFORMANCE* 📊\n\n"
        "*Monthly Performance (Last 6 Months):*\n"
        "• January: +32.7%\n"
        "• February: +28.4%\n"
        "• March: +18.1%\n"
        "• April: +25.3%\n"
        "• May: +52.3%\n"
        "• June: +40.36%\n\n"
        "*Performance by Currency Pair:*\n"
        "• EUR/USD: +29.8%\n"
        "• GBP/USD: +31.2%\n"
        "• USD/JPY: +26.7%\n"
        "• XAU/USD: +19.41%\n\n"
        "*Key Performance Metrics:*\n"
        "• Win Rate: 80%\n"
        "• Profit Factor: 3.2\n"
        "• Average Win/Loss Ratio: 3.5\n"
        "• Maximum Drawdown: 8.3%\n"
        "• Recovery Factor: 4.8\n\n"
        "Our EA has been consistently profitable across different market conditions. These results are verified and can be demonstrated in a live account."
    )
    
    keyboard = [
        [InlineKeyboardButton("🤖 How Our EA Works", callback_data='ea_how_works')],
        [InlineKeyboardButton("💰 EA Pricing Plans", callback_data='ea_pricing')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_to_ea_funnel')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await update.callback_query.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending EA performance stats: {str(e)}")
        # Fallback: try to send a new message to the chat if reply_text fails
        try:
            chat_id = update.effective_chat.id
            await update.callback_query.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def send_ea_explanation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain how the EA works."""
    # Check if message is available
    if update.callback_query.message is None:
        logger.warning("Message is no longer available for EA explanation")
        return
        
    message = (
        "🤖 *HOW OUR EA TRADING BOT WORKS* 🤖\n\n"
        "*Trading Strategy:*\n"
        "Our EA uses a proprietary multi-timeframe analysis algorithm that combines:\n"
        "• Advanced price action patterns\n"
        "• Key support/resistance levels\n"
        "• Market structure analysis\n"
        "• Volatility-based entry/exit timing\n\n"
        "*Risk Management:*\n"
        "• Fixed 1% risk per trade\n"
        "• Dynamic stop-loss placement\n"
        "• Trailing take-profit mechanism\n"
        "• Anti-drawdown protection\n\n"
        "*Technical Specifications:*\n"
        "• Compatible with MT4/MT5\n"
        "• Works with any broker\n"
        "• Trades FX majors and Gold\n"
        "• Fully automated - set and forget\n"
        "• 24/5 operation during market hours\n\n"
        "*Setup Process:*\n"
        "1. We help you set up the EA on your account\n"
        "2. Configure risk parameters to your preference\n"
        "3. Regular updates and optimization\n"
        "4. Ongoing technical support\n\n"
        "Our EA is designed to be hands-off while maintaining professional risk management standards."
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 View Performance Stats", callback_data='ea_stats')],
        [InlineKeyboardButton("💰 EA Pricing Plans", callback_data='ea_pricing')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_to_ea_funnel')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await update.callback_query.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending EA explanation: {str(e)}")
        # Fallback: try to send a new message to the chat if reply_text fails
        try:
            chat_id = update.effective_chat.id
            await update.callback_query.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def send_ea_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show EA pricing options with clear next steps."""
    # Check if message is available
    if update.callback_query.message is None:
        logger.warning("Message is no longer available for EA pricing")
        return
        
    keyboard = [
        [InlineKeyboardButton("🔄 Monthly Plan - $200", callback_data='purchase_monthly')],
        [InlineKeyboardButton("⭐ Quarterly Plan - $500 (Save 15%)", callback_data='purchase_quarterly')],
        [InlineKeyboardButton("🔥 Annual Plan - $1500 (Save 30%)", callback_data='purchase_annual')],
        [InlineKeyboardButton("💰 Copytrade Option - $500 Lifetime", callback_data='purchase_copytrade')],
        [InlineKeyboardButton("❓ Questions? Chat with Support", url='https://t.me/trump_tnetc_admin')],
        [InlineKeyboardButton("🔙 Back to EA Info", callback_data='back_to_ea_funnel')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await update.callback_query.message.reply_text(
            "📈 *TNETC EA Pricing Plans*\n\n"
            "Choose your preferred plan to start automated trading with our 80% win-rate system:"
            "\n\nAll plans include:\n"
            "✅ Full EA setup assistance\n"
            "✅ 24/7 technical support\n"
            "✅ Performance monitoring\n"
            "✅ Regular updates\n\n"
            "*Monthly Plan:* Perfect for trying our system\n"
            "*Quarterly Plan:* Our most popular option\n"
            "*Annual Plan:* Best value for serious traders\n"
            "*Copytrade Option:* We trade for you - no technical setup needed\n\n"
            "Select a plan below to get started:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending EA pricing: {str(e)}")
        # Fallback: try to send a new message to the chat if reply_text fails
        try:
            chat_id = update.effective_chat.id
            await update.callback_query.bot.send_message(
                chat_id=chat_id,
                text="📈 *TNETC EA Pricing Plans*\n\n"
                "Choose your preferred plan to start automated trading with our 80% win-rate system:"
                "\n\nAll plans include:\n"
                "✅ Full EA setup assistance\n"
                "✅ 24/7 technical support\n"
                "✅ Performance monitoring\n"
                "✅ Regular updates\n\n"
                "*Monthly Plan:* Perfect for trying our system\n"
                "*Quarterly Plan:* Our most popular option\n"
                "*Annual Plan:* Best value for serious traders\n"
                "*Copytrade Option:* We trade for you - no technical setup needed\n\n"
                "Select a plan below to get started:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def send_signal_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send Signal performance results with proof images."""
    # Check if message is available
    if update.callback_query.message is None:
        logger.warning("Message is no longer available for Signal results")
        chat_id = update.effective_chat.id
        if not chat_id:
            logger.error("Could not determine chat ID for Signal results")
            return
        
    message = (
        "📊 *TNETC SIGNAL PERFORMANCE RESULTS* 📊\n\n"
        "*Last Month Performance:*\n"
        "• Forex: +40.36% ✅\n"
        "• Gold: +19.41% ✅\n"
        "• Combined Win Rate: 94% 🚀\n\n"
        "*Signal Frequency:*\n"
        "• 1-3 signals per day\n"
        "• Each with detailed entry, TP, and SL levels\n"
        "• Multi-timeframe analysis included\n\n"
        "*Risk Management:*\n"
        "• Recommended 1-2% risk per trade\n"
        "• Average risk-reward ratio: 1:3\n"
        "• Detailed trade management instructions\n\n"
        "Get our premium signals combined with EA trading in our Premium VIP Signal + EA Trading Bot package!"
    )
    
    keyboard = [
        [InlineKeyboardButton("💎 Premium VIP Signal + EA Bundle", callback_data='premium_vip_ea')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_to_signal_welcome')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.callback_query.message:
            msg = await update.callback_query.message.reply_text(
                message, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

        # Send 3 random proof images
        try:
            proof_images = [f for f in os.listdir(PROOF_IMAGES_DIR) if f.lower().endswith('.jpg')]
            selected_images = random.sample(proof_images, min(3, len(proof_images)))
            
            for img_file in selected_images:
                img_path = os.path.join(PROOF_IMAGES_DIR, img_file)
                with open(img_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=msg.chat_id,
                        photo=photo,
                        caption="📈 Real Member Profit Proof",
                        parse_mode='Markdown'
                    )
        except Exception as img_error:
            logger.error(f"Error sending proof images: {str(img_error)}")

    except Exception as e:
        logger.error(f"Error sending Signal results: {str(e)}")
        # Fallback: try to send a new message to the chat if reply_text fails
        try:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def send_vip_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send VIP benefits details."""
    # Check if message is available
    if update.callback_query.message is None:
        logger.warning("Message is no longer available for VIP benefits")
        chat_id = update.effective_chat.id
        if not chat_id:
            logger.error("Could not determine chat ID for VIP benefits")
            return
    
    message = (
        "💎 *PREMIUM VIP SIGNAL + EA TRADING BOT BENEFITS* 💎\n\n"
        "*Exclusive Access:*\n"
        "• Private VIP-only Telegram group\n"
        "• Direct access to professional traders\n"
        "• Priority support 24/7\n\n"
        "*Enhanced Trading:*\n"
        "• Expert 1-on-1 signal guidance\n"
        "• High-performance EA trading bot (80% win rate)\n"
        "• VIP-only signals with higher win rates\n"
        "• Advanced entry/exit strategies\n"
        "• Priority notification for market-moving events\n\n"
        "*Education & Growth:*\n"
        "• Advanced trading documentation\n"
        "• Monthly strategy sessions\n"
        "• Performance reviews and optimization\n\n"
        "*Premium Package Pricing:*\n"
        "• Monthly: $400/month\n"
        "• Quarterly: $1000 (Save 16%)\n"
        "• Annual: $3000 (Save 37%)\n\n"
        "Join our Premium VIP + EA package and elevate your trading to the next level!"
    )
    
    keyboard = [
        [InlineKeyboardButton("💎 Get Premium VIP + EA Bundle", callback_data='premium_vip_ea')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_to_vip_welcome')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.callback_query.message:
            await update.callback_query.message.reply_text(
                message, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
        else:
            # Fallback if message is None
            chat_id = update.effective_chat.id
            await update.callback_query.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error sending VIP benefits: {str(e)}")
        # Fallback: try to send a new message to the chat if reply_text fails
        try:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    error_details = {
        "error_type": type(context.error).__name__,
        "error_message": str(context.error),
        "timestamp": datetime.now().isoformat()
    }
    
    if update:
        log_user_interaction(update, "error", error_details)
    else:
        logger.error(f"Update caused error: {json.dumps(error_details, indent=2)}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Sorry, something went wrong. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")

async def get_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to get database statistics."""
    # Check if user is admin
    admin_ids = [123456789]  # Replace with actual admin IDs
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Get user count
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            # Get interaction count
            cursor.execute("SELECT COUNT(*) FROM interactions")
            interaction_count = cursor.fetchone()[0]
            
            # Get purchase count
            cursor.execute("SELECT COUNT(*) FROM purchases")
            purchase_count = cursor.fetchone()[0]
            
            # Get follow-up stats
            cursor.execute("SELECT status, COUNT(*) FROM followups GROUP BY status")
            followup_stats = cursor.fetchall()
            
            # Get campaign stats
            cursor.execute("SELECT campaign, COUNT(*) FROM users WHERE campaign IS NOT NULL GROUP BY campaign")
            campaign_stats = cursor.fetchall()
            
            # Format stats message
            stats_message = (
                "*TNETC Bot Statistics*\n\n"
                f"Total Users: {user_count}\n"
                f"Total Interactions: {interaction_count}\n"
                f"Total Purchases: {purchase_count}\n\n"
                "*Follow-up Statistics:*\n"
            )
            
            for status, count in followup_stats:
                stats_message += f"• {status.capitalize()}: {count}\n"
            
            stats_message += "\n*Campaign Statistics:*\n"
            
            for campaign, count in campaign_stats:
                stats_message += f"• {campaign}: {count}\n"
            
            await update.message.reply_text(stats_message, parse_mode='Markdown')
        except Error as e:
            logger.error(f"Database query error: {e}")
            await update.message.reply_text(f"Error retrieving statistics: {str(e)}")
        finally:
            conn.close()
    else:
        await update.message.reply_text("Error connecting to database.")

async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to get information about a specific user."""
    # Check if user is admin
    admin_ids = [123456789]  # Replace with actual admin IDs
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    # Check if user ID is provided
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a user ID. Usage: /user_info [user_id]")
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID. Please provide a numeric ID.")
        return
    
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Get user info
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                await update.message.reply_text(f"User with ID {user_id} not found.")
                return
            
            # Get user's services viewed
            cursor.execute("SELECT service, view_count, last_viewed FROM services_viewed WHERE user_id = ?", (user_id,))
            services = cursor.fetchall()
            
            # Get user's purchases
            cursor.execute("SELECT plan_code, purchase_date, price FROM purchases WHERE user_id = ?", (user_id,))
            purchases = cursor.fetchall()
            
            # Get user's follow-ups
            cursor.execute("SELECT service, scheduled_date, status, response FROM followups WHERE user_id = ?", (user_id,))
            followups = cursor.fetchall()
            
            # Format user info message
            user_info = (
                f"*User Information for ID {user_id}*\n\n"
                f"Username: @{user[1] or 'None'}\n"
                f"Name: {user[2] or ''} {user[3] or ''}\n"
                f"Join Date: {user[4]}\n"
                f"Last Interaction: {user[5]}\n"
                f"Purchased: {'Yes' if user[6] == 1 else 'No'}\n"
                f"Campaign: {user[7] or 'None'}\n\n"
            )
            
            if services:
                user_info += "*Services Viewed:*\n"
                for service, view_count, last_viewed in services:
                    user_info += f"• {service.capitalize()}: {view_count} views (last: {last_viewed})\n"
                user_info += "\n"
            
            if purchases:
                user_info += "*Purchases:*\n"
                for plan, date, price in purchases:
                    user_info += f"• {plan} ({price}) on {date}\n"
                user_info += "\n"
            
            if followups:
                user_info += "*Follow-ups:*\n"
                for service, date, status, response in followups:
                    user_info += f"• {service.capitalize()}: {status} on {date}"
                    if response:
                        user_info += f" (Response: {response})"
                    user_info += "\n"
            
            await update.message.reply_text(user_info, parse_mode='Markdown')
        except Error as e:
            logger.error(f"Database query error: {e}")
            await update.message.reply_text(f"Error retrieving user information: {str(e)}")
        finally:
            conn.close()
    else:
        await update.message.reply_text("Error connecting to database.")

async def export_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to export user data to a CSV file."""
    # Check if user is admin
    admin_ids = [123456789]  # Replace with actual admin IDs
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Get all users
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.last_name, u.join_date, u.last_interaction, 
                       u.purchased, u.campaign, COUNT(DISTINCT p.id) as purchase_count
                FROM users u
                LEFT JOIN purchases p ON u.user_id = p.user_id
                GROUP BY u.user_id
            """)
            users = cursor.fetchall()
            
            if not users:
                await update.message.reply_text("No users found in the database.")
                return
            
            # Create CSV file
            import csv
            from io import StringIO
            
            csv_file = StringIO()
            csv_writer = csv.writer(csv_file)
            
            # Write header
            csv_writer.writerow([
                'User ID', 'Username', 'First Name', 'Last Name', 'Join Date', 
                'Last Interaction', 'Purchased', 'Campaign', 'Purchase Count'
            ])
            
            # Write user data
            for user in users:
                csv_writer.writerow(user)
            
            # Send CSV file
            csv_file.seek(0)
            await update.message.reply_document(
                document=csv_file.getvalue().encode(),
                filename='tnetc_users.csv',
                caption=f"Exported {len(users)} users."
            )
        except Error as e:
            logger.error(f"Database query error: {e}")
            await update.message.reply_text(f"Error exporting users: {str(e)}")
        finally:
            conn.close()
    else:
        await update.message.reply_text("Error connecting to database.")

async def send_premium_vip_ea_details(update, context):
    """Send details about the Premium VIP with EA Trading Bot bundle."""
    query = update.callback_query
    
    message = (
        "*💎 Premium VIP Signal + EA Trading Bot 💎*\n\n"
        "Our most comprehensive package combining premium VIP signals and our high-performance EA trading bot.\n\n"
        "*What's Included:*\n"
        "✅ Expert 1-on-1 signal guidance\n"
        "✅ High-performance EA trading bot (80% win rate)\n"
        "✅ VIP copy trading with higher returns\n"
        "✅ 24/7 VIP support\n"
        "✅ Private VIP-only Telegram group\n"
        "✅ Advanced entry/exit strategies\n"
        "✅ Priority notification for market-moving events\n"
        "✅ Monthly strategy sessions\n"
        "✅ Regular EA updates and optimization\n\n"
        "*Premium Package Pricing:*\n"
        "• Monthly: $400/month\n"
        "• Quarterly: $1000 (Save 16%)\n"
        "• Annual: $3000 (Save 37%)\n\n"
        "To get started with this premium package, contact our support team."
    )
    
    keyboard = [
        [InlineKeyboardButton("📱 Contact Support", url='https://t.me/trump_tnetc_admin')],
        [InlineKeyboardButton("✅ I've Made Payment", callback_data='payment_made_premium_vip_ea')],
        [InlineKeyboardButton("🔙 Back to Plans", callback_data='show_all_services')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if query.message:
            await query.message.reply_text(
                message, 
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Fallback if message is None
            chat_id = update.effective_chat.id
            await query.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error sending premium VIP+EA details: {str(e)}")
        # Fallback: try to send a new message to the chat if reply_text fails
        try:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as inner_e:
            logger.error(f"Fallback message also failed: {str(inner_e)}")

async def send_testimonial_to_user(context, chat_id, service):
    """Send testimonial images to a user from the testimonial_images directory."""
    logger.info(f"Sending testimonial to user {chat_id} for service {service}")
    
    try:
        # Get all testimonial images
        image_files = [f for f in os.listdir(TESTIMONIAL_IMAGES_DIR) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg')) and not f.startswith('.')]
        
        if not image_files:
            logger.warning("No testimonial images found in directory")
            return
            
        # Select random images (2-3)
        num_images = random.randint(2, 3)
        selected_images = random.sample(image_files, min(num_images, len(image_files)))
        
        # Create engaging captions
        testimonial_captions = [
            "🔥 *Another member just posted:* \"I'm up $7,890 this week using the signals!\"",
            "💰 *VIP Member results:* \"Just hit my first $10K profit day thanks to this group!\"",
            "📈 *Verified member:* \"I've already made back 5x what I paid for this service!\"",
            "🚀 *Member testimonial:* \"These signals are insanely accurate - 8/10 winners today!\"",
            "💯 *Just in:* \"Been using the EA for 2 weeks and already up 37% - incredible!\"",
            "⚡️ *Member feedback:* \"This is the only trading group that consistently delivers!\"",
            "🏆 *Top performer:* \"Turned $5K into $22K in just one month following these signals\"",
            "🔐 *VIP member:* \"Finally found a service that actually delivers as promised!\""
        ]
        
        # Prepare the message text
        intro_message = "*🔥 Latest Results from Our Community 🔥*\n\nMembers are crushing it with our exclusive signals & EA bot...\n\n"
        
        # Send intro message
        await context.bot.send_message(
            chat_id=chat_id,
            text=intro_message,
            parse_mode='Markdown'
        )
        
        # Send images individually instead of as a group
        for img_file in selected_images:
            img_path = os.path.join(TESTIMONIAL_IMAGES_DIR, img_file)
            caption = random.choice(testimonial_captions)
            
            # Open the file in binary mode
            with open(img_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode='Markdown'
                )
        
        # Send call to action
        keyboard = [
            [InlineKeyboardButton("🔥 Join VIP Now (Limited Spots)", callback_data="premium_vip_ea")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="*⏰ Don't Miss Out! Our special promotion ends soon!*\n\nSecure your spot now before prices increase!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error sending testimonial: {str(e)}")

def main() -> None:
    """Start the bot."""
    try:
        # Validate token before starting the bot
        token = validate_token()
        
        # Create the Application and pass it your bot's token
        application = Application.builder().token(token).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_click))
        
        # Add admin command handlers
        application.add_handler(CommandHandler("stats", get_stats))
        application.add_handler(CommandHandler("user_info", get_user_info))
        application.add_handler(CommandHandler("export_users", export_users))
        # Remove or implement the other commands if needed
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Ensure job queue is initialized
        if not application.job_queue:
            logger.warning("Job queue not initialized. Creating job queue...")
            application.job_queue = JobQueue()
            application.job_queue.set_application(application)
            application.job_queue.start()
            logger.info("Job queue started successfully")

        # Start the Bot
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except InvalidToken:
        logger.error("Invalid token provided. Please check your bot token and try again.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()