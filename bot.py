from data import *
import telebot
import re
from time import sleep
import os

bot = telebot.TeleBot(os.environ['BOT_TOKEN'], threaded=False)
DEBUG_CHAT_ID = os.environ['DEBUG_CHAT_ID']

WEEK_DAYS = ('ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА', 'ВОСКРЕСЕНЬЕ')
HASHTAG_VALIDATOR = re.compile(r"\s*(#([a-zA-Z0-9А-я]+)(?:_(\w+))?)\s*$")


def format_message(text):
    s = text.lstrip()
    if s.startswith("📝") or s.startswith("📰") or s.startswith("📓"):
        return None

    lines = text.split('\n')
    day = lines[0].rstrip().lstrip()
    if day.upper() in WEEK_DAYS:
        if len(lines) > 1 and HASHTAG_VALIDATOR.match(lines[-1]):
            del lines[-1]
        del lines[0]
        return f"📝 <b>{day.capitalize()}:</b>\n" + ''.join([f'🖊 {s}\n' for s in lines]) + '#расписание'

    m = HASHTAG_VALIDATOR.match(lines[-1])
    if m is None:
        return None  # Нечего менять и редактировать

    if m[2].upper() == 'НОВОСТИ' and m[3] is None:
        del lines[-1]
        return "📰 <b>Новости:</b>\n" + ''.join([f'➕ {s}\n' for s in lines]) + m[1]

    if m[2] == 'англ':
        first_name = 'Английский язык'
    elif m[2] == 'ОБЖ':
        first_name = 'ОБЖ'
    else:
        first_name = m[2].capitalize()

    second_name = '' if m[3] is None else ' (%s)' % m[3]
    first_line = f"📓 <b>{first_name}{second_name}:</b>\n"
    lines.pop()
    return first_line + ''.join([f'🖊 {s}\n' for s in lines]) + m[1]


INDEX_GETTER = re.compile(r"([a-zA-Z])(\d+)")
INDEX_NUMBER_GETTER = re.compile(r"(\d)_(-?\+?\d+)")
POWER_GETTER = re.compile(r"\^(-?\+?\d+)")
POWER_BRCKTS_GETTER = re.compile(r"\^\((-?\+?\d+)\)")
ROOT_CONST_GETTER = re.compile(r"(\w+)\(\s*(\d+)\s*\)")


def math_format(text):
    def repl_by_dict(string, dct):
        for key in dct:
            string = string.replace(key, dct[key])
        return string

    text = POWER_GETTER.sub(lambda m: repl_by_dict(m[1], power_sym), text)
    text = POWER_BRCKTS_GETTER.sub(lambda m: m[1].translate(power_sym), text)
    text = INDEX_GETTER.sub(lambda m: m[1] + repl_by_dict(m[2], index_sym), text)
    text = INDEX_NUMBER_GETTER.sub(lambda m: m[1] + repl_by_dict(m[2], index_sym), text)

    def repl_root_const(m):
        lower = m[1].lower()
        if lower in root_const_sym:
            return f"{root_const_sym[lower]}{m[2]}"
        else:
            return m[0]

    text = ROOT_CONST_GETTER.sub(repl_root_const, text)
    text = repl_by_dict(text, spec_main_sym)
    text = repl_by_dict(text, spec_full_sym)
    text = repl_by_dict(text, op_sym)
    for regex, new in func_sym:
        text = re.sub(regex, new, text, flags=re.IGNORECASE)
    for s in const_sym:
        text = re.sub(s, const_sym[s], text, flags=re.IGNORECASE)
    return text


@bot.channel_post_handler(content_types=["text"])
def formatter(message):
    out = format_message(message.html_text)
    if out:
        bot.edit_message_text(out, chat_id=message.chat.id, message_id=message.message_id, parse_mode='HTML')


def text_to_html(text):
    return text.replace("&", "&amp").replace("<", "&lt").replace(">", "&gt")


def dict_to_table(d: dict):
    keys = d.keys()
    max_len = max(map(lambda s: len(s), keys))
    text = ""
    for key in keys:
        text += f"<code>{text_to_html(key)}</code> <code>{' ' * (max_len - len(key))}:" \
                f"  {text_to_html(d[key])}</code>\n"
    return text


def split_lines(text, lines_for_msg):
    out_lines = [""]
    msg_lines_no = 1
    for line in text.split('\n'):
        if msg_lines_no > lines_for_msg:
            msg_lines_no = 1
            out_lines.append("")
        else:
            msg_lines_no += 1
        out_lines[-1] += f'\n{line}'
    return out_lines


@bot.message_handler(commands=['start', 'help'])
def helps(message):
    if ' ' in message.text:
        bot.send_message(message.chat.id, message.text)

    text = "<b>Основные Макросы:</b>\n(Основаны на TeX)\n\n"
    text += dict_to_table(spec_main_sym)
    bot.send_message(message.chat.id, text, parse_mode='HTML')

    text = "\n<b>Греческие Символы:</b>\n\n"
    text += dict_to_table(greek_sym)
    bot.send_message(message.chat.id, text, parse_mode='HTML')

    text = "\n<b>Операторы:</b>\n\n"
    text += dict_to_table(op_sym)
    text += "\n<b>Функции:</b>\n\n"
    text += dict_to_table(root_const_sym)
    text += "\n<b>Константы:</b>\n\n"
    text += dict_to_table(const_sym)
    text += "\nА так же поддерживаются индексы и степени (с помощью <code>^</code>)"
    text += "\nЕсли между двумя числами стоит <code>_</code>," \
            " то второе считается индексом первого (для указания основания системы счисления)"
    text += "\nПолный список макросов можно получить командой <code>/macros</code>"

    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['macros'])
def macro_list(message):
    text = "<b>Все Макросы:</b>\n(Основаны на TeX)\n\n"
    text += dict_to_table(spec_full_sym)
    for msg_text in split_lines(text, 50):
        bot.send_message(message.chat.id, msg_text, parse_mode='HTML')


@bot.message_handler(content_types=["text"])
def formatter(message):
    if message.chat.id == DEBUG_CHAT_ID:
        try:
            if '\n' in message.text:
                exec(message.text)
                bot.send_message(message.chat.id, "---> executed <---")
            else:
                bot.send_message(message.chat.id, repr(eval(message.text)))
        except BaseException as e:
            bot.send_message(message.chat.id, repr(e))
    else:
        print(f"msg={message.text}")
        bot.send_message(message.chat.id, math_format(message.text))


@bot.inline_handler(lambda query: True)
def query_text(inline_query):
    fmt = math_format(inline_query.query)
    r = telebot.types.InlineQueryResultArticle('article', 'Отфоматировать', telebot.types.InputTextMessageContent(fmt),
                                               description=fmt,
                                               thumb_url="https://i.ibb.co/Q8tzWhm/pi.png",
                                               )
    bot.answer_inline_query(inline_query.id, [r],
                            cache_time=0,
                            switch_pm_text="Помощь",
                            switch_pm_parameter="_")


if __name__ == '__main__':
    bot.send_message(DEBUG_CHAT_ID, "---> bot reloaded <---")
    while True:
        try:
            bot.polling(none_stop=True, interval=0.8)
        except BaseException as e:
            print(e)
            bot.send_message(DEBUG_CHAT_ID, repr(e))
            sleep(0.8)
