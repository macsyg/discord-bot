import os, discord, json, math, random
import structure as str
from discord import voice_client
from discord.ext import commands
import youtube_dl

TOKEN = os.getenv('TOKEN')
PREFIX = os.getenv('PREFIX')


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
        print(message.content + ' --- ' + status.quiz.song_title)
        if message.content == 'skip' or message.content == 'pass':
            status.add_skip(message.author.name)
            await message.channel.send(content=(f'Skips: {status.quiz.skips}/{status.quiz.skips_needed}'))
        
        if status.quiz.skips >= status.quiz.skips_needed:
            await message.channel.send(content=('**Song skipped**'))
            await message.channel.send(content=('It was: ' + f'**{status.quiz.song_title}**'))
            status.clear_skips()
            ctx = await client.get_context(message)
            ctx.voice_client.stop()

        if message.content.lower() == status.quiz.song_title:
            status.guess_song(message.author.name)
            await message.channel.send(content=(f'{message.author.name}! Correct!'))

            ctx = await client.get_context(message)
            ctx.voice_client.stop()

    # elif message.content == 'test':
    #     ctx = await client.get_context(message)
    #     ctx.voice_client.stop()

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
        ytdl_url_opts = {'format': 'bestaudio', 
                         'age_limit': 30}
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
    status.queue = []
    await ctx.voice_client.disconnect()


@client.command()
async def skip(ctx):
    if ctx.voice_client is None:
        return
    ctx.voice_client.stop()


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
        try:
            await ctx.voice_client.disconnect()
        except:
            pass


async def play_song(ctx, song):
    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    # -ss HH:MM:SS.ss czas, od którego ma polecieć piosenka

    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_opts)
    try:
        ctx.voice_client.play(source, 
                              after=lambda error: client.loop.create_task(check_queue(ctx))) # ta linijka daje mozliwosc puszczenia nastepnej piosenki 

        # ctx.voice_client.play(source, after=None)
        await ctx.message.channel.send(content=('Currently playing: ' + song['title']), 
                                       delete_after=10)
    except:
        await ctx.message.channel.send(content=('Error'), 
                                       delete_after=10)


async def quiz(ctx):
    elem = None
    with open('./data.json', 'r') as f:
        data = json.load(f)
        elem = data.pop(0)
        data.append(elem)
        with open('./data.json', 'w') as f1:
            f1.write(json.dumps(data, indent=4))

    ytdl_url_opts = {'format': 'bestaudio', 
                         'age_limit': 30}
    try:
        info = youtube_dl.YoutubeDL(ytdl_url_opts).extract_info(elem['link'], download=False)
    except:
        await quiz(ctx)

    status.incr_quiz_song_id()

    print(status.quiz.song_id)
    if status.quiz.song_id > status.quiz.size:
        await ctx.message.channel.send(content=('Quiz ended'))
        await ctx.message.channel.send(content=(status.show_leaderboard()))
        await ctx.voice_client.disconnect()
        return

    song = {
        'title': info['title'],
        'url': info['formats'][0]['url']
    }

    status.set_title(elem['title'])
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


@client.command()
async def custom(ctx):
    if ctx.voice_client is not None:
        return
    else:
        voice_channel = ctx.message.author.voice.channel
        await voice_channel.connect()

    status.change_mode('quiz')
    context = ctx.message.content.replace('.custom ', '')
    args = context.split(' ')

    if len(args) > 0:
        if len(args) > 1:
            status.set_quiz(size = int(args[0]), skips = int(args[1]))
        else:
            status.set_quiz(size = int(args[0]))

    with open('./data.json', 'r') as f:
        data = json.load(f)

        current_index = len(data)
        while current_index != 0:
            # Pick a remaining element...
            random_index = math.floor(random.random() * current_index)
            current_index -= 1
        
            # And swap it with the current element.
            [data[current_index], data[random_index]] = [
            data[random_index], data[current_index]]

        with open('./data.json', 'w') as f1:
            f1.write(json.dumps(data, indent=4))  

    if not ctx.voice_client.is_playing():
        await quiz(ctx)

        




# @client.command()
# async def doktor(ctx):
#     if ctx.voice_client is None:
#         return
    
#     voice_channel = ctx.message.author.voice.channel
#     await voice_channel.connect()

#     info = await search_song('jungle girl bass boosted extreme')

#     song = {
#         'title': info['formats'][0]['url'],
#         'url': info['title']
#     }

#     ffmpeg_jggirl_opts = {
#         'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
#         'options': '-vn -ss 00:02:12.75 -t 8'
#     }

#     source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_jggirl_opts)

client.run(TOKEN)