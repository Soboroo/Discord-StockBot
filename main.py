import asyncio
import io
import json
import random
import plotly.graph_objects as go
import plotly.io

import aiohttp
import discord
import requests
from discord.ext import commands, tasks
import datetime
import pandas as pd
from pykrx import stock
from urllib import parse

client = commands.Bot(command_prefix=['s!', 'ㅈ!', '주!', '주식!', 'ㅈㅅ!'], help_command=None)
KST = datetime.timedelta(hours=9)


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    print((datetime.datetime.now() + KST).strftime('%H시 %M분 %S초'))

    @tasks.loop(seconds=1)
    async def market_time():
        now = (datetime.datetime.now() + KST).time().replace(microsecond=0)
        txt = ''
        if now < datetime.time(8, 30):
            txt = "개장 전"
        elif datetime.time(8, 30) <= now < datetime.time(8, 40):
            txt = "시간 외, 동시호가"
        elif datetime.time(8, 40) <= now < datetime.time(9, 0):
            txt = "동시호가"
        elif datetime.time(9, 0) <= now < datetime.time(15, 30):
            txt = "정규시간"
        elif datetime.time(15, 20) <= now < datetime.time(15, 30):
            txt = "정규시간, 동시호가"
        elif datetime.time(15, 30) <= now < datetime.time(15, 40):
            txt = "시간 외 접수"
        elif datetime.time(15, 40) <= now < datetime.time(16, 0):
            txt = "시간 외"
        elif datetime.time(16, 0) <= now < datetime.time(18, 00):
            txt = "시간 외 단일가"
        elif now >= datetime.time(18, 0):
            txt = "장 마감"

        await client.change_presence(status=discord.Status.online, activity=discord.Game(txt))

    market_time.start()


@client.command()
async def help(ctx):
    embed = discord.Embed(title="명령어 목록", description="prefix: `s!\n"
                                                      "graph <종목이름> <기간 | optional>: <종목이름>의 그래프를 출력합니다.\n"
                                                      "- <기간> 종류: 일(default), 월, 3(개)월, 연(년), 3년\n"
                                                      "trends <종목이름> <거래 유형 | optional>: <종목이름>의 투자자별 매매 현황을 출력합니다.\n"
                                                      "- <거래 유형> 종류: 순매수(default), 매수, 매도\n"
                                                      "제작자: Soboroo#4869")
    await ctx.send(embed=embed)


@client.command(name='그래프')
async def graph(ctx, arg='', time=''):
    term = ''

    if arg == '':
        await ctx.send("종목명을 입력해주세요.")
        return

    x = await getFromNaver(ctx, arg)
    if x == 0:
        return

    day = datetime.datetime.today().strftime('%Y%m%d')
    day1 = (datetime.datetime.today() - datetime.timedelta(days=5)).strftime('%Y%m%d')
    df = stock.get_market_ohlcv_by_date(day1, day, x)

    price = df.iloc[-1, 3]
    diff = price - df.iloc[-2, 3]
    per = round(diff / df.iloc[-2, 3] * 100, 2)

    if diff > 0:
        color = 0xf51818
        diff_txt = '▲' + str(diff)
    elif diff < 0:
        color = 0x1b61d1
        diff_txt = '▼' + str(-1 * diff)
    else:
        color = 0xFFFFFF
        diff_txt = str(diff)
    txt = ''
    if time == '일' or time == '':
        term = 'd'
        txt = '일일'
    elif time == '월':
        term = 'm'
        txt = '월간'
    elif time == '3월' or time == '3개월':
        term = 'm3'
        txt = '3개월'
    elif time == '년' or time == '연':
        term = 'y'
        txt = '연간'
    elif time == '3년':
        term = 'y3'
        txt = '3년'
    else:
        await ctx.send("기간 입력이 잘못되었습니다.")
        await ctx.send("기간 종류: 일(default), 월, 3(개)월, 연(년), 3년")

    embed = discord.Embed(title=f"{arg} {txt}그래프",
                          description=f"**{price}**\n{diff_txt}원 {per}%\n[상세차트](https://finance.daum.net/chart/A{x})",
                          color=color)
    embed.set_footer(text=f'차트 기간 인수: 일, 월, 3(개)월, 년(연), 3년')
    embed.set_image(url=f"https://t1.daumcdn.net/finance/chart/kr/daumstock/{term}/A{x}.png")
    await ctx.send(embed=embed)


@client.command(name='동향')
async def trends(ctx, arg, arg1=''):
    if arg == '':
        await ctx.send("종목명을 입력해주세요.")
        return

    x = await getFromNaver(ctx, arg)
    if x == 0:
        return

    day = datetime.datetime.today().strftime('%Y%m%d')
    day1 = (datetime.datetime.today() - datetime.timedelta(days=7)).strftime('%Y%m%d')
    df = pd.DataFrame(stock.get_market_trading_volume_by_date(day1, day, x, on=arg1)).sort_values(by=['날짜'],
                                                                                                  ascending=False).head()

    result = ''
    temp = f"{'%-8s' % '날짜'}{'%7s' % '기관합계'}{'%7s' % '기타법인'}{'%8s' % '개인'}{'%6s' % '외국인합계'}{'%8s' % '전체'}"
    result += f"{temp}\n"
    for column_name, item in df.iterrows():
        temp = f"{'%-10s' % column_name.date()}{'%10d' % item['기관합계']}{'%10d' % item['기타법인']}{'%10d' % item['개인']}{'%10d' % item['외국인합계']}{'%10d' % item['전체']}"
        result += f"{temp}\n"

    if arg1 == '':
        txt = '순매수'
    else:
        txt = arg1

    embed = discord.Embed(title=f"{arg} 투자자별 {txt}동향", description=f"(단위: 주)```{result}```")

    if arg1 == '':
        embed.set_footer(text="차트 속성 인수: 매도, 매수, 순매수")

    await ctx.send(embed=embed)


async def getFromNaver(ctx, name):
    response = requests.get(
        f'https://ac.finance.naver.com/ac?_callback=window.mycallback&q={parse.quote(name)}&q_enc=euc-kr&st=111&frm=stock&r_format=json&r_enc=euc-kr&r_unicode=0&t_koreng=1&r_lt=111').text
    jsonObject = json.loads(response.replace('window.mycallback(', '').replace('})', '}'))
    jsonArray = jsonObject['items'][0]

    try:
        if str(jsonArray[0][1][0]) == name:
            return jsonArray[0][0][0]
        else:
            result = ''
            for item in jsonArray:
                result += f'{item[1][0]}: {item[0][0]}\n'

            embed = discord.Embed(title='검색 결과', description=f'```{result}```')
            await ctx.send(embed=embed)

            return 0
    except IndexError:
        await ctx.send('검색 결과를 찾을 수 없습니다.')
        return 0


def getUpbitCode(name, currency='원화'):
    response = requests.get('https://api.upbit.com/v1/market/all').text
    jsonObject = json.loads(response)

    if currency == '원화':
        currency = 'KRW'
    elif currency == '비트코인':
        currency = 'BTC'
    for item in jsonObject:
        if item["market"][:3] == currency and item["korean_name"] == name:
            return item["market"]

    return -1


@client.command(name='코인')
async def coingraph(ctx, name, currency='원화'):
    market = getUpbitCode(name, currency)

    if market == -1:
        await ctx.send('검색 결과를 찾을 수 없습니다.')
        return
    else:
        embed = make_embed(name, market)
        return await ctx.send(file=discord.File('fig.png'), embed=embed)

        #if name == '도지코인':
        #    async with aiohttp.ClientSession() as session:
        #        image = shiba()
        #        async with session.get(image[0]) as resp:
        #            if resp.status != 200:
        #                return await ctx.send('Could not download file...')
        #            data = io.BytesIO(await resp.read())
        #            await ctx.send(file=discord.File(data, 'shiba.' + image[1]))


@client.command()
async def trackGraph(ctx, name, currency='원화', time=60):
    market = getUpbitCode(name, currency)
    message = await coingraph(ctx, name, currency)
    if time > 600:
        await ctx.send('최대 지속 시간: 600초')
        time = 600

    @tasks.loop(seconds=5)
    async def track(arg):
        await arg.edit(embed=make_embed(name, market))

    track.start(message)
    await asyncio.sleep(float(time))
    track.stop()


def makeGraph(market):
    params = {"market": market, "count": "50"}
    response = requests.get('https://api.upbit.com/v1/candles/minutes/1', params=params).text
    jsonObject = json.loads(response)

    open_data = []
    high_data = []
    low_data = []
    close_data = []
    dates = []

    for item in jsonObject:
        open_data.append(item["opening_price"])
        high_data.append(item["high_price"])
        low_data.append(item["low_price"])
        close_data.append(item["trade_price"])
        dates.append(datetime.datetime.fromisoformat(item["candle_date_time_kst"]))

    fig = go.Figure(data=[go.Candlestick(x=dates, open=open_data, high=high_data, low=low_data, close=close_data, increasing_line_color='#C34042', decreasing_line_color='#0966C6')])
    fig.update_layout(xaxis_rangeslider_visible=False, paper_bgcolor="#2F3136", font_color="#FFFFFF", plot_bgcolor="#1A2436", font_size=30, margin_t=0)
    fig.update_xaxes(gridcolor='#1F2B40')
    fig.update_yaxes(gridcolor='#1F2B40')
    plotly.io.write_image(fig=fig, file='fig.png', engine='kaleido', width=1920, height=1080)


def make_embed(name, market):
    makeGraph(market)
    querystring = {"markets": market}
    response = requests.get("https://api.upbit.com/v1/ticker", params=querystring).text
    jsonObject = json.loads(response)

    if jsonObject[0]['change'] == 'RISE':
        color = 0xf51818
        diff_txt = '▲'
    elif jsonObject[0]['change'] == 'FALL':
        color = 0x1b61d1
        diff_txt = '▼'
    else:
        color = 0xFFFFFF
        diff_txt = ''

    embed = discord.Embed(title=f"{name} 캔들그래프",
                          description=f"**{jsonObject[0]['trade_price']}**\n{diff_txt}{jsonObject[0]['change_price']}원 {round(jsonObject[0]['signed_change_rate'] * 100, 2)}%",
                          color=color)
    embed.set_image(url='attachment://fig.png')
    return embed

def shiba():
    inu = [[
        'https://img1.daumcdn.net/thumb/R720x0/?fname=https://t1.daumcdn.net/section/oc'
        '/219dbea2a6684ed8ba9327a2b40c6f70',
        'jpg'],
        [
            'https://lh3.googleusercontent.com/proxy/I0Yb3dVEwRJZULBkZfi1iMHTEs_lGJp2yABzGAXpEEOl0sxvPifvwVqS'
            '-kZur4sFWo7gXUlwV8xzmBb2VMW3JtRrE80I9C9oi7D3yQCvjC63jHJG5cGSL3g_'
            'OQCsYduYEZsKIAlUycIEQxbqXmZBwKVdiHk0JDIxOMsETvnH',
            'jpg'],
        [
            'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSX5mFOUe2kh'
            '-CslpsE3RZSbw2s93g5dDGRCeT4VpONtcsVAGok9d4de-1piF12rFc8KYY&usqp=CAU',
            'jpg'],
        ['https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR98boC9Z0h-kst-CCI05r8f9taB-cXc97H0Q&usqp=CAU',
         'jpg'],
        ['https://pbs.twimg.com/profile_images/487547286130393088/9jBo19wP_400x400.jpeg', 'jpg'],
        [
            'https://img1.daumcdn.net/thumb/R720x0/?fname=http%3A%2F%2Ft1.daumcdn.net%2Fsection%2Foc'
            '%2Fa8855a3201f8436aad0797f92ef0ae64',
            'jpg'],
        [
            'https://img1.daumcdn.net/thumb/R720x0/?fname=http%3A%2F%2Ft1.daumcdn.net%2Fliveboard%2Fshare'
            '%2Fefecdbbd6bb54d22bd9823e2d802ddb2.png',
            'png'],
        ['https://t1.daumcdn.net/liveboard/share/0ee37597964743a0926451e27e83fdae.gif', 'gif']]

    return random.choice(inu)


client.run("") # Your Bot Token
