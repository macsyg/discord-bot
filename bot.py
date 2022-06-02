import os, discord, json, math, random
import structure as str
from discord import voice_client
from discord.ext import commands
import youtube_dl

TOKEN = os.getenv('TOKEN') # your discord bot token generated through Discord Developers Portal
PREFIX = os.getenv('PREFIX') # any prefix you want that will make bot recognize command use


client = commands.Bot(command_prefix=PREFIX)
status = str.Status()

@client.event
async def on_ready():
    print('Online')


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if status.mode == 'quiz':
        print(message.content + ' --- ' + status.quiz.current_song_title)

        if message.content.lower() == status.quiz.current_song_title and status.quiz.current_song_guessed == False:
            status.quiz.guess_song(message.author.mention)
            await message.channel.send(content=(f'{message.author.mention} guessed!'))
            await message.channel.send(content=(f'**Songs played**: {status.quiz.song_id} / {status.quiz.size}'))
            await message.channel.send(content=(f'**Title**: {status.quiz.current_song_title}'))
            await message.channel.send(content=(f'**URL**: {status.quiz.current_song_url}'))

            status.quiz.incr_song_id()

            ctx = await client.get_context(message)
            ctx.voice_client.stop()

        if message.content == 'skip' or message.content == 'pass':
            status.quiz.add_skip(message.author.name)
            await message.channel.send(content=(f'**Skips**: {status.quiz.skips}/{status.quiz.skips_needed}'))
        
            if status.quiz.skips >= status.quiz.skips_needed:
                await message.channel.send(content=('**Song skipped**'))
                await message.channel.send(content=(f'**Title**: {status.quiz.current_song_title}'))
                await message.channel.send(content=(f'**URL**: {status.quiz.current_song_url}'))

                status.quiz.incr_song_id()
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
            'format': 'bestaudio', 
            'age_limit': 30
        }
        info = youtube_dl.YoutubeDL(ytdl_url_opts).extract_info(query, download=False)

    song = {
        'title': info['title'],
        'url': info['formats'][0]['url']
    }

    song_title = song['title']
    print(f'Queued: {song_title}')   
    await ctx.message.channel.send(content=('Queued: ' + song['title']), 
                                   delete_after=10)

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


async def search_song(name):
    ytdl_query_opts = {'format' : 'bestaudio', 
                       'quiet' : True, 
                       'age_limit': 30}

    info = await client.loop.run_in_executor(None, 
                                             lambda: youtube_dl.YoutubeDL(ytdl_query_opts).extract_info(f'ytsearch{1}:{name}', 
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

    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_opts)
    try:
        ctx.voice_client.play(source, 
                              after=lambda error: client.loop.create_task(check_queue(ctx))) # after song ends or something goes wrong try playing next song 

        await ctx.message.channel.send(content=('Currently playing: ' + song['title']), 
                                       delete_after=10)
    except:
        await ctx.message.channel.send(content=('Error'), 
                                       delete_after=10)
        print('Error')


async def quiz(ctx):
    elem = None
    with open('./data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        elem = data.pop(0)
        data.append(elem)
        with open('./data.json', 'w', encoding='utf-8') as f1:
            f1.write(json.dumps(data, indent=4))

    ytdl_url_opts = {
        'format': 'bestaudio', 
        'age_limit': 30
    }

    try:
        info = youtube_dl.YoutubeDL(ytdl_url_opts).extract_info(elem['link'], download=False)
    except:
        await quiz(ctx)

    if status.quiz.song_id > status.quiz.size:
        await ctx.message.channel.send(content=(status.quiz.show_leaderboard()))
        await ctx.voice_client.disconnect()
        status.change_mode('afk')
        return

    print(status.quiz.song_id)

    song = {
        'title': info['title'],
        'url': info['formats'][0]['url']
    }

    status.quiz.set_song(elem['title'], elem['link'])
    await quiz_song(ctx, song)


async def quiz_song(ctx, song):
    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_opts)

    try:
        ctx.voice_client.play(source, after=lambda error: client.loop.create_task(quiz(ctx)))
    except:
        await ctx.message.channel.send(content=('Error'), 
                                       delete_after=10)
        print('Error')


@client.command()
async def start_quiz(ctx):
    if status.mode == 'music':
        return
        
    args = ctx.message.content.split(' ')
    args.pop(0)

    print(args)

    try:
        if len(args) > 0:
            custom_size = int(args[0])
            if len(args) > 1:
                custom_skips = int(args[1])
                status.quiz.set_quiz(size = custom_size, skips = custom_skips)
            else:
                status.quiz.set_quiz(size = custom_size)
    except:
        await ctx.message.channel.send(content=('Wrong values'), 
                                       delete_after=10)
        return

    status.change_mode('quiz')
    voice_channel = ctx.message.author.voice.channel
    await voice_channel.connect()

    with open('./data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

        current_index = len(data)
        while current_index != 0:
            random_index = math.floor(random.random() * current_index)
            current_index -= 1
            [data[current_index], data[random_index]] = [data[random_index], data[current_index]]

        with open('./data.json', 'w', encoding='utf-8') as f1:
            f1.write(json.dumps(data, indent=4))  

    if not ctx.voice_client.is_playing():
        await quiz(ctx)

@client.command()
async def stop_quiz(ctx):
    await ctx.voice_client.disconnect()

    status.change_mode('afk')

    await ctx.message.channel.send(content=(status.quiz.show_leaderboard()))


client.run(TOKEN)