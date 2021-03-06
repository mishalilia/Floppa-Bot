# Ссылка на добавление бота на сервер
# https://discord.com/api/oauth2/authorize?client_id=834805615896297543&permissions=8&scope=bot

import discord
import os
import youtube_dl
from asyncio import sleep
from discord.ext import commands


bot = commands.Bot(command_prefix='*')

# Убираем стандартную команду help
bot.remove_command('help')

queue = {}
is_repeating = {}
audio_index = {}


@bot.event
async def on_ready():
    print('Floppa Bot готов.\n\n')

    await bot.change_presence(activity=discord.Game(name='Для помощи напишите *help'))


@bot.command(name='help', aliases=['commands'])
async def help(ctx):
    await ctx.send(embed=discord.Embed(title='Команды:',
                                       description='`*join` - присоединиться к голосовому каналу\n'
                                                   '`*play` ***ссылка/название видео '
                                                   'на YouTube*** - включить видео\n'
                                                   '`*skip` - пропустить текущее видео\n'
                                                   '`*repeat` - повторять очередь\n'
                                                   '`*leave` - остановить воспроизведение\n',
                                       colour=0xa84300))
    print(f'\n{ctx.author} запросил правила.\n')


@bot.command(name='join')
async def join(ctx):
    try:
        if ctx.author.voice.channel is not None:
            voice_channel = ctx.author.voice.channel
            try:
                await voice_channel.connect()
            except Exception:
                for i in bot.voice_clients:
                    if i.guild == ctx.guild:
                        voice_connection = i
                await voice_connection.move_to(voice_channel)

            print(f'Подключился к голосовому каналу к {ctx.author}')
        else:
            await ctx.send(':x: **Вы должны находиться в голосовом канале**')
    except Exception:
        await ctx.send(':x: **Вы должны находиться в голосовом канале**')


@bot.command(name='play', aliases=['p'])
async def play(ctx, *, video='Пусто'):
    if video == 'Пусто':
        await ctx.send(':x: **Напишите после команды название или ссылку на видео**')
        return None
    elif ctx.author.voice is None:
        await ctx.send(':x: **Вы должны находиться в голосовом канале**')
        return None
    else:
        message = await ctx.send('Загрузка...')

        # Подключаемся к каналу, если уже не подключены
        voice_channel = ctx.author.voice.channel
        try:
            await voice_channel.connect()
        except Exception:
            pass

        # Ищем подключение к нужному каналу
        voice_connection = None
        for i in bot.voice_clients:
            if i.channel == voice_channel:
                voice_connection = i

        if voice_connection is None:
            await ctx.send(':x: **Вы должны находиться в голосовом канале с ботом**')
            return None

        # Параметры аудио
        ydl_opts = {
            'format': 'bestaudio',
            'noplaylist': True,
            'continue_dl': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192', }]
        }

        # Скачиваем видео
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                if 'youtube.com' not in video:
                    videos = ydl.extract_info(f"ytsearch3:{video}", download=False)['entries']
                    video_info = {'view_count': 0}
                    for i in videos:
                        if i['view_count'] > video_info['view_count']:
                            video_info = i
                else:
                    video_info = ydl.extract_info(video, download=False)
        except Exception:
            await ctx.send(':x: **Не смог найти такое видео**')
            await message.delete()
            return None

        global queue, is_repeating
        try:
            queue[ctx.guild.id] += [(video_info, ctx.author, ctx)]
        except Exception:
            queue[ctx.guild.id] = [(video_info, ctx.author, ctx)]
            is_repeating[ctx.guild.id] = False

        await message.delete()

        if len(queue[ctx.guild.id]) > 1:
            await ctx.send(embed=discord.Embed(title=f'Добавил: **{video_info["title"]}**'
                                                     f' в очередь на позицию **{len(queue[ctx.guild.id])}**',
                                               description=f'Запросил: {ctx.author.mention}', colour=0xa84300))
            print(f'Добавил {video_info["title"]} в очередь на позицию {len(queue[ctx.guild.id])} \n'
                  f'Запросил: {ctx.author}')
        else:
            await ctx.send(embed=discord.Embed(title=f'{video_info["title"]}',
                                               description=f'Запросил: {ctx.author.mention}',
                                               colour=0xa84300, url=video_info['webpage_url']))

            # Включаем аудио
            FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
            audio = discord.FFmpegPCMAudio(video_info['formats'][0]['url'], **FFMPEG_OPTS)
            voice_connection.play(source=audio)

            # Ждем пока видео доиграет
            while voice_connection.is_playing():
                await sleep(1)
            # Включаем следующее видео в очереди
            await next_song(ctx, voice_connection)

            print(f'\n{ctx.author} запросил включить {video_info["title"]}\n')


@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    try:
        voice_connection = None
        for i in bot.voice_clients:
            if i.channel == ctx.author.voice.channel:
                voice_connection = i
    except Exception:
        await ctx.send(':x: **Вы должны находиться в голосовом канале с ботом**')
        print(f'\n{ctx.author} попытался пропустить видео.\n')

    if ctx.author.voice is None or voice_connection is None:
        await ctx.send(':x: **Вы должны находиться в голосовом канале с ботом**')
        print(f'\n{ctx.author} попытался пропустить видео.\n')
    else:
        global queue
        if len(queue[ctx.guild.id]) != 0:
            voice_connection.stop()
            print(f'\n{ctx.author} пропустил видео.\n')
        else:
            print(f'\n{ctx.author} попытался пропустить видео.')
            await ctx.send(':x: **Очередь не занята**')


@bot.command(name='repeat')
async def repeat(ctx):
    global is_repeating

    voice_connection = None
    for i in bot.voice_clients:
        if i.channel == ctx.author.voice.channel:
            voice_connection = i
    if ctx.author.voice is None or voice_connection is None:
        await ctx.send(':x: **Вы должны находиться в голосовом канале с ботом**')
        print(f'\n{ctx.author} попытался поставить очередь на повторение.\n')
    elif voice_connection.is_playing() is True:
        if is_repeating[ctx.guild.id]:
            is_repeating[ctx.guild.id] = False
            await ctx.send(embed=discord.Embed(description=f'{ctx.author.mention} убрал очередь с повторения.',
                                               colour=0xa84300))
            print(f'\n{ctx.author} убрал очередь с повторения.\n')
        else:
            is_repeating[ctx.guild.id] = True
            await ctx.send(embed=discord.Embed(description=f'{ctx.author.mention} поставил очередь на повторение.',
                                               colour=0xa84300))
            print(f'\n{ctx.author} поставил очередь на повторение.\n')
    else:
        await ctx.send(embed=discord.Embed(description='Очередь пуста.',
                                           colour=0xa84300))
        print(f'\n{ctx.author} попытался поставить очередь на повторение.\n')


@bot.command(name='leave')
async def leave(ctx):
    try:
        voice_connection = None
        for i in bot.voice_clients:
            if i.channel == ctx.author.voice.channel:
                voice_connection = i
    except Exception:
        await ctx.send(':x: **Вы должны находиться в голосовом канале с ботом**')
        print(f'\n{ctx.author} попытался остановить вопроизведение.\n')

    if ctx.author.voice is None or voice_connection is None:
        await ctx.send(':x: **Вы должны находиться в голосовом канале с ботом**')
        print(f'\n{ctx.author} попытался остановить вопроизведение.\n')
    else:
        await voice_connection.disconnect()
        global queue, is_repeating
        queue[ctx.guild.id] = []
        is_repeating[ctx.guild.id] = False
        print(f'\n{ctx.author} остановил вопроизведение.\n')


async def next_song(ctx, voice_connection):
    global queue, is_repeating, audio_index
    if is_repeating[ctx.guild.id] is False:
        del queue[ctx.guild.id][0]
    else:
        if queue[ctx.guild.id]:
            try:
                audio_index[ctx.guild.id] += 1
            except Exception:
                audio_index[ctx.guild.id] = 1
        if audio_index[ctx.guild.id] == len(queue[ctx.guild.id]):
            audio_index[ctx.guild.id] = 0
    if queue[ctx.guild.id]:
        if is_repeating[ctx.guild.id] is False:
            video_info = queue[ctx.guild.id][0][0]
            author = queue[ctx.guild.id][0][1]
            ctx = queue[ctx.guild.id][0][2]
        else:
            video_info = queue[ctx.guild.id][audio_index[ctx.guild.id]][0]
            author = queue[ctx.guild.id][audio_index[ctx.guild.id]][1]
            ctx = queue[ctx.guild.id][audio_index[ctx.guild.id]][2]
        await ctx.send(embed=discord.Embed(title=f'{video_info["title"]}',
                                           description=f'Запросил: {ctx.author.mention}',
                                           colour=0xa84300, url=video_info['webpage_url']))

        # Включаем аудио
        FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        audio = discord.FFmpegPCMAudio(video_info['formats'][0]['url'], **FFMPEG_OPTS)
        voice_connection.play(source=audio)
        while voice_connection.is_playing():
            await sleep(1)
        await next_song(ctx, voice_connection)

        print(f'\n{author} запросил включить {video_info["title"]}\n')


bot.run(os.environ['BOT_TOKEN'])
