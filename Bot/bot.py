import telebot
import json
from telebot import types
import requests
import subprocess
import requests  # Ensure requests is imported at the top of your file
import datetime

TOKEN = '________'  #yourbottoken
bot = telebot.TeleBot(TOKEN)


last_run_time = None


def create_invite_link(chat_id):
    url = f'https://api.telegram.org/bot{TOKEN}/createChatInviteLink'
    payload = {'chat_id': chat_id}
    response = requests.post(url, json=payload)
    result = response.json()
    if result['ok']:
        return result['result']['invite_link']
    else:
        return "Error: Could not create invite link"


# Hardcoded password for demonstration. Change it to a more secure password in production.
ADMIN_PASSWORD = "12345"
def private_chat_only(func):
    def wrapper(message):
        if message.chat.type != "private":
            return  # Ignore messages not from a private chat
        return func(message)
    return wrapper

@bot.message_handler(commands=['start'])
@private_chat_only
def send_welcome(message):
    welcome_text = (
        f"👋 Hi {message.from_user.first_name}!   Nice to see you."+"\n"+"Here’s what I can help you with:\n\n"
        " **/begin** - Set up your account🚀.\n"
        " **/stats** - View  stats about your personal linkages📊.\n\n"
        " "
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')
    
    # Store user data in a JSON file named id_name.json
    user_info = {'user_id': message.from_user.id, 'name': message.from_user.first_name}
    try:
        with open('id_name.json', 'r+') as file:
            users = json.load(file)
            users.append(user_info)
            file.seek(0)
            json.dump(users, file, indent=4)
    except (FileNotFoundError, json.JSONDecodeError):
        with open('id_name.json', 'w') as file:
            json.dump([user_info], file, indent=4)


@bot.message_handler(commands=['begin'])
@private_chat_only
def handle_begin(message):
    try:
        with open('group_ids.json', 'r') as file:
            groups = json.load(file)
        markup = types.InlineKeyboardMarkup(row_width=1)  # Create an inline keyboard
        # Create a button for each group and add to the markup
        for group in groups:
            button = types.InlineKeyboardButton(group['name'], callback_data=f"select_{group['id']}")
            markup.add(button)
        # Send a message with the inline keyboard
        bot.send_message(message.chat.id, "Choose from the following groups:", reply_markup=markup)
    except FileNotFoundError:
        bot.send_message(message.chat.id, "No group data available.")
    except json.JSONDecodeError:
        bot.send_message(message.chat.id, "Error reading group data.")
    # Store user data in a JSON file named id_name.json
    user_info = {'user_id': message.from_user.id, 'name': message.from_user.first_name}
    try:
        with open('id_name.json', 'r+') as file:
            users = json.load(file)
            users.append(user_info)
            file.seek(0)
            json.dump(users, file, indent=4)
    except (FileNotFoundError, json.JSONDecodeError):
        with open('id_name.json', 'w') as file:
            json.dump([user_info], file, indent=4)

@bot.message_handler(commands=['stats'])
@private_chat_only
def handle_stats(message):
    global last_run_time
    chat_id = message.chat.id
    current_time = datetime.datetime.now()
    
    # Check if subprocess ran within the last hour
    if last_run_time and (current_time - last_run_time).total_seconds() < 3600:
        # If it's been less than an hour, skip running the subprocess
        try:
            with open('updated_users.json', 'r') as file:
                users = json.load(file)
            send_user_stats(chat_id, users)
        except FileNotFoundError:
            bot.send_message(chat_id, "Stats file not found. Please try again later.")
        except json.JSONDecodeError:
            bot.send_message(chat_id, "Error reading stats file.")
    else:
        # If more than an hour has passed, run subprocess and update the time
        try:
            subprocess.run(['python3', 'count.py'], check=True)
            last_run_time = current_time  # Update the last run time
            with open('updated_users.json', 'r') as file:
                users = json.load(file)
            send_user_stats(chat_id, users)
        except subprocess.CalledProcessError:
            bot.send_message(chat_id, "Failed to execute count.py")
        except FileNotFoundError:
            bot.send_message(chat_id, "Stats file not found. Please try again later.")
        except json.JSONDecodeError:
            bot.send_message(chat_id, "Error reading stats file.")

def send_user_stats(chat_id, users):
    # Assumes 'group_ids.json' is available and properly formatted
    try:
        with open('group_ids.json', 'r') as file:
            groups = json.load(file)
            group_dict = {str(group['id']): group['name'] for group in groups}

        response_message = "📊 Your Stats:\n\n"
        # Filter the list to find entries matching the user's chat_id
        user_data = [user for user in users if user['chat_id'] == chat_id]
        for data in user_data:
            group_name = group_dict.get(str(data['group_id']), "Unknown Group")
            user_entry = (
                f"👥 Group Name: {group_name}\n"
                f"💼 Wallet ID: {data['wallet_id']}\n"
                f"🔗 Invite Link: {data['invite_link']}\n"
                f"<b>🔢Linkings Count:</b> {data['join_count']}\n"
                "----------------------------------------\n"
            )
            response_message += user_entry

        if user_data:
            bot.send_message(chat_id, response_message, parse_mode='HTML', disable_web_page_preview=True)
        else:
            bot.send_message(chat_id, "No statistics available for your account.", parse_mode='Markdown')
            
    except FileNotFoundError:
        bot.send_message(chat_id, "Data file not found.")
    except json.JSONDecodeError:
        bot.send_message(chat_id, "Error reading data from file.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_group_selection(call):
    group_id = call.data.split('_')[1]
    # Check if the bot is admin in the group
    chat_member = bot.get_chat_member(group_id, bot.get_me().id)
    if not chat_member.status == 'administrator':
        bot.send_message(call.message.chat.id, "Contact the admins about my admin privileges.")
    else:
        msg = bot.send_message(call.message.chat.id, "Please enter your wallet ID:")
        bot.register_next_step_handler(msg, process_wallet_id, group_id)
    bot.answer_callback_query(call.id)

def process_wallet_id(message, group_id):
    wallet_id = message.text

    # Define the function to check Solana wallet existence
    def check_solana_wallet_existence(wallet_address):
        api_key = '_____________________' #your alchemy api key
        url = f'https://solana-mainnet.g.alchemy.com/v2/{api_key}/getBalance'
        headers = {'Content-Type': 'application/json'}
        payload = {'jsonrpc': '2.0', 'method': 'getBalance', 'params': [wallet_address, {"commitment": "confirmed"}], 'id': 1}

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get('error'):
                return False
            elif data['result']['value'] is not None:
                return True  # Wallet exists if there's a balance or the account is recognized
            return False
        except requests.RequestException:
            return False

    # Check if the provided wallet ID exists in the Solana blockchain
    if not check_solana_wallet_existence(wallet_id):
        msg = bot.send_message(message.chat.id, "Invalid wallet address. Please send a correct wallet address.")
        bot.register_next_step_handler(msg, process_wallet_id, group_id)
        return

    group_name = "Unknown Group"  # Default if group not found
    
    # Load group names from group_ids.json and find the matching group name
    try:
        with open('group_ids.json', 'r') as file:
            groups = json.load(file)
        group_name = next((group['name'] for group in groups if str(group['id']) == group_id), "Unknown Group")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        bot.send_message(message.chat.id, f"Error loading group data: {str(e)}")

    # Generate a new invite link
    invite_link = create_invite_link(group_id)

    # Store the details in user.json
    user_info = {
        'chat_id': message.chat.id,
        'group_id': group_id,
        'wallet_id': wallet_id,
        'invite_link': invite_link
    }

    try:
        with open('user.json', 'r+') as file:
            users = json.load(file)
            users.append(user_info)
            file.seek(0)
            json.dump(users, file)
    except FileNotFoundError:
        with open('user.json', 'w') as file:
            json.dump([user_info], file)
    
    # Construct the message with the link, wallet ID, and group name
# Construct the message with the link, wallet ID, and group name using HTML formatting
    response_message = (
      f"<b>🔗 Invite Link:</b> {invite_link}\n"+"\n"
      f"<b>💼 Wallet ID:</b> {wallet_id}\n"
      f"<b>👥 Group Name:</b> {group_name}"
)

# Send message with HTML formatting enabled
    bot.send_message(message.chat.id, response_message, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(commands=['admindash'])
@private_chat_only
def request_password(message):
    msg = bot.send_message(message.chat.id, "Please enter the admin password:")
    bot.register_next_step_handler(msg, verify_password)

def verify_password(message):
    # Delete the message where the user sent the password
    bot.delete_message(message.chat.id, message.message_id)
    
    if message.text == ADMIN_PASSWORD:
        # Password is correct, proceed to show the dashboard
        show_admin_dashboard(message)
    else:
        # Password is incorrect, deny access
        bot.send_message(message.chat.id, "Incorrect password. Access denied.")

def show_admin_dashboard(message):
    chat_id = message.chat.id

    # Execute count.py as a subprocess
    try:
        subprocess.run(['python3', 'count.py'], check=True)
    except subprocess.CalledProcessError:
        bot.send_message(chat_id, "Failed to execute count.py")
        return

    try:
        # Load user information from id_name.json
        with open('id_name.json', 'r') as file:
            users = json.load(file)
            user_dict = {user['user_id']: user['name'] for user in users}
    except (FileNotFoundError, json.JSONDecodeError):
        bot.send_message(chat_id, "User file not found or is corrupt.")
        return

    try:
        # Load groups information
        with open('group_ids.json', 'r') as file:
            groups = json.load(file)
            group_dict = {str(group['id']): group['name'] for group in groups}

        # Load updated user data
        with open('updated_users.json', 'r') as file:
            updated_users = json.load(file)
        
        response_message = "<b>📊 All User Entries:</b>\n\n"
        for data in updated_users:
            # Fetch the user's name using the chat ID and the group name using group ID
            user_name = user_dict.get(data['chat_id'], "Unknown User")
            group_name = group_dict.get(str(data['group_id']), "Unknown Group")

            user_entry = (
                f"<b>👤 Name:</b> {user_name}\n"
                f"<b>👥 Group Name:</b> {group_name}\n"
                f"<b>💼 Wallet ID:</b> <code>{data['wallet_id']}</code>\n"
                f"<b>🔗 Invite Link:</b> {data['invite_link']}\n"
                f"<b>🔢 Join Count:</b> {data['join_count']}\n"
                "----------------------------------------\n"
            )
            response_message += user_entry
        
        # Send the compiled entries in a well-formatted single message
        bot.send_message(chat_id, response_message, parse_mode='HTML', disable_web_page_preview=True)
    except FileNotFoundError:
        bot.send_message(chat_id, "Data file not found.")
    except json.JSONDecodeError:
        bot.send_message(chat_id, "Error reading data from file.")



@bot.message_handler(content_types=['new_chat_members'])

def handle_new_member(message):
    new_members = message.new_chat_members
    for member in new_members:
        if member.id == bot.get_me().id:
            chat_id = message.chat.id
            chat_name = message.chat.title
            try:
                with open('group_ids.json', 'r') as file:
                    groups = json.load(file)
            except FileNotFoundError:
                groups = []
            if chat_id not in [group['id'] for group in groups]:
                groups.append({'id': chat_id, 'name': chat_name})
                with open('group_ids.json', 'w') as file:
                    json.dump(groups, file)


print(bot.get_me())
bot.infinity_polling()