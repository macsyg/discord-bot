import os, discord, json, math, random
from dotenv import load_dotenv
import structure as str
from discord import voice_client
from discord.ext import commands
import yt_dlp

from difflib import SequenceMatcher

from threading import Lock

load_dotenv()
TOKEN = os.getenv('TOKEN') # your discord bot token generated through Discord Developers Portal
PREFIX = os.getenv('PREFIX') # any prefix you want that will make bot recognize command use

QUIZ_FILE = os.getenv('QUIZ_FILE')


client = commands.Bot(command_prefix=PREFIX, intents = discord.Intents.all())
status = str.Status()
lock = Lock()

@client.event
async def on_ready():
    print('Online')


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()    


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if status.mode == 'quiz':
        print(message.content + ' --- ' + status.quiz.current_song_title)

        if message.content[0] == '.':
            pass

        elif message.content == 'skip' or message.content == 'pass':
            status.quiz.add_skip(message.author.name)
            await message.channel.send(content=(f'**Skips**: {status.quiz.skips}/{status.quiz.skips_needed}'))
        
            if status.quiz.skips >= status.quiz.skips_needed:

                print('skipped')
                skip_embed = discord.Embed(
                    title = f'**It was**:',
                    description = f'[**{status.quiz.current_song_title}**]({status.quiz.current_song_url})\n' +
                    f'Songs: {status.quiz.song_id}/{status.quiz.size}\n' +
                    '**Song was skipped**',
                )

                await message.channel.send(embed = skip_embed)

                status.quiz.time_passed = False
                status.quiz.clear_skips()
                
                ctx = await client.get_context(message)
                ctx.voice_client.stop()


        elif similar(message.content.lower(), status.quiz.current_song_title.lower()) > 0.9 and status.quiz.current_song_guessed == False:
            status.quiz.guess_song(message.author.mention)

            guess_embed = discord.Embed(
                title = f'**It was**:',
                description = f'[**{status.quiz.current_song_title}**]({status.quiz.current_song_url})\n' +
                f'Songs: {status.quiz.song_id}/{status.quiz.size}\n' +
                (f'{message.author.mention} **guessed!**'),
            )

            await message.channel.send(embed = guess_embed)

            status.quiz.time_passed = False
            status.quiz.clear_skips()

            ctx = await client.get_context(message)
            ctx.voice_client.stop()

    await client.process_commands(message)


@client.command()
@commands.is_owner()
async def shutdown(ctx):
    status.queue = []

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()

    await ctx.bot.close()


@client.command()
async def play(ctx):
    if status.mode == 'quiz':
        return

    status.change_mode('music')

    query = ctx.message.content.replace('.play ', '')

    if ctx.voice_client is None:
        voice_channel = ctx.message.author.voice.channel
        await voice_channel.connect()
    elif ctx.voice_client.channel != ctx.message.author.voice.channel:
        return await ctx.message.channel.send('Bot is occupied')

    info = None
    if not ('youtube.com/watch?' in query or 'https://youtu.be/' in query):
        info = await search_song(query)
        if info is None:
            return await ctx.message.channel.send('No song found')
    else:
        ytdl_url_opts = {
            'format' : 'bestaudio', 
            'quiet' : True, 
            'age_limit': 30,
            'allow_unplayable_formats': False
        }
        info = yt_dlp.YoutubeDL(ytdl_url_opts).extract_info(query, download=False)

    song = {
        'title': info['title'],
        'url': info['url'],
        'original_url': info['original_url']
    }

    song_title = info['title']
    song_url = info['original_url']

    song_embed = discord.Embed(
        title = f'Queued:',
        description = f'[**{song_title}**]({song_url})'
    )
    await ctx.message.channel.send(embed = song_embed, delete_after=10)

    status.queue.append(song)

    if not ctx.voice_client.is_playing():
        await check_queue(ctx)


@client.command()
async def stop(ctx):
    if status.mode == 'quiz':
        return

    status.queue = []
    await ctx.voice_client.disconnect()
    status.change_mode('afk')


@client.command()
async def skip(ctx):
    if status.mode == 'quiz':
        return
    
    if ctx.voice_client is None:
        return

    ctx.voice_client.stop()
    status.change_mode('afk')

@client.command()
async def queue(ctx):
    q = status.queue
    num_elems = len(q)
    q = q[:10]

    q_str = []
    i = 1
    for song in q:
        title = song['title']
        url = song['original_url']
        msg = f'{i}: ' + f'[**{title}**]({url})\n'
        q_str.append(msg)
        i += 1

    queue_str = " ".join(q_str)

    queue_embed = discord.Embed(
        title = f'Next songs:',
        description = queue_str +
        ("...\n" if num_elems > 10 else "") + 
        f'Songs in queue: {num_elems}\n'
    )

    await ctx.message.channel.send(embed = queue_embed)


async def search_song(name):
    ytdl_query_opts = {
        'format' : 'bestaudio', 
        'quiet' : True, 
        'age_limit': 30,
        'allow_unplayable_formats': False
    }

    info = await client.loop.run_in_executor(None, 
                                             lambda: yt_dlp.YoutubeDL(ytdl_query_opts).extract_info(f'ytsearch{1}:{name}', 
                                             download=False, 
                                             ie_key='YoutubeSearch'))
                                             
    with open('./response.json', 'w') as f:
        f.write(json.dumps(info, indent=4))
                       
    if info['entries']:
        return info['entries'][0]
    else:
        return None


async def check_queue(ctx):
    if status.queue != []:
        song = status.queue.pop(0)

        song_title = song['title']
        print(f'        Currently playing: {song_title}')

        await play_song(ctx, song)
    else:
        status.change_mode('afk')
        try:
            await ctx.voice_client.disconnect()
        except:
            pass


async def play_song(ctx, song):
    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    # "-ss HH:MM:SS.ss" <- this flag, when added to options, starts the song at requested moment

    print(song['url'])
    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_opts)
    try:
        ctx.voice_client.play(source, 
                              after=lambda error: client.loop.create_task(check_queue(ctx))) # after song ends or something goes wrong try playing next song 

        song_title = song['title']
        song_url = song['original_url']
        song_embed = discord.Embed(
            title = f'Currently playing:',
            description = f'[**{song_title}**]({song_url})'
        )
        await ctx.message.channel.send(embed = song_embed, delete_after=10)
    except:
        await ctx.message.channel.send(content=('Error'), 
                                       delete_after=10)
        print('Error')


async def quiz(ctx):

    if status.mode != 'quiz':
        return

    if status.quiz.time_passed:
        guess_embed = discord.Embed(
            title = f'**It was**:',
            description = f'[**{status.quiz.current_song_title}**]({status.quiz.current_song_url})\n' +
            f'Songs: {status.quiz.song_id}/{status.quiz.size}\n' +
            ('**Time passed!**'),
        )
        status.quiz.clear_skips()
        status.quiz.time_passed = False

        await ctx.message.channel.send(embed = guess_embed)

    if not status.quiz.unavailable:
        status.quiz.incr_song_id()
    else:
        status.quiz.unavailable = False

    elem = None
    with open(QUIZ_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        elem = data.pop(0)
        data.append(elem)
        with open(QUIZ_FILE, 'w', encoding='utf-8') as f1:
            f1.write(json.dumps(data, indent=4))

    ytdl_url_opts =  {
        'format' : 'bestaudio', 
        'quiet' : True, 
        'age_limit': 30,
        'allow_unplayable_formats': False
    }

    try:
        info = yt_dlp.YoutubeDL(ytdl_url_opts).extract_info(elem['url'], download=False)
    except:
        await quiz(ctx)

    if status.quiz.song_id > status.quiz.size:
        await ctx.message.channel.send(content=(status.quiz.show_leaderboard()))
        await ctx.voice_client.disconnect()
        status.change_mode('afk')
        return

    print(status.quiz.song_id)


    what_to_guess = "title"

    song = {
        'title': info['title'],
        'url': info['url'],
        'duration': info['duration_string']
    }

    status.quiz.set_song(elem[what_to_guess], elem['url'])
    await quiz_song(ctx, song)


async def quiz_song(ctx, song):

    mins_secs = song['duration'].split(':')
    seconds = int(mins_secs[-1]) + int(mins_secs[-2]) * 60

    clip_start = random.randint(seconds//4, seconds//2)
    clip_start_mins, clip_start_secs = clip_start//60, clip_start%60

    # print(clip_start_mins, clip_start_secs, type(clip_start_mins), type(clip_start_secs))

    clip_start_mins = f'{clip_start_mins}' if clip_start_mins > 9 else f'0{clip_start_mins}'
    clip_start_secs = f'{clip_start_secs}' if clip_start_secs > 9 else f'0{clip_start_secs}'


    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': f'-vn -ss 00:{clip_start_mins}:{clip_start_secs}.00 -t 00:00:30.00',
    }

    # "-ss HH:MM:SS.ss" <- this flag, when added to options, starts the song at requested moment

    try:
        source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_opts)
    except:
        print('Song not available:', song['title'])
        status.quiz.unavailable = True

    try:
        ctx.voice_client.play(source, after=lambda error: client.loop.create_task(quiz(ctx)))
    except:
        await ctx.message.channel.send(content=('Error'), 
                                       delete_after=10)
        print('Error')


@client.command()
async def start_quiz(ctx, size = 30, skips = 1):
    if status.mode == 'music':
        return


    try:
        status.quiz.set_quiz(size, skips)
    except:
        await ctx.message.channel.send(content=('Wrong values'), 
                                       delete_after=10)
        return

    status.change_mode('quiz')
    voice_channel = ctx.message.author.voice.channel
    await voice_channel.connect()

    with open(QUIZ_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

        current_index = len(data)
        while current_index != 0:
            random_index = math.floor(random.random() * current_index)
            current_index -= 1
            [data[current_index], data[random_index]] = [data[random_index], data[current_index]]

        with open(QUIZ_FILE, 'w', encoding='utf-8') as f1:
            f1.write(json.dumps(data, indent=4))  

    if not ctx.voice_client.is_playing():
        await quiz(ctx)

@client.command()
async def stop_quiz(ctx):
    await ctx.voice_client.disconnect()

    status.change_mode('afk')

    await ctx.message.channel.send(content=(status.quiz.show_leaderboard()))

client.run(TOKEN)