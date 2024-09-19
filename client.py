from tcp_quick.client import Client, Connect
import traceback
import sounddevice as sd
import asyncio
from scipy.signal import convolve
import numpy as np

# 如果你想要使用ssl,请取消下面的注释
import ssl


class MyClient(Client):

    SAMPLE_RATE = 44100  # 采样率
    CHANNELS = 1  # 声道数
    CHUNK_SIZE = 256  # 每次读取的数据块大小

    async def _link(self) -> None:
        # 初始化异步队列
        self.audio_queue = asyncio.Queue()
        # 启动音频流处理
        self._loop.create_task(self._start_audio_stream())
        return await super()._link()

    async def _handle(self, connect: Connect) -> None:
        # 处理从队列中接收到的数据
        while True:
            indata = await self.audio_queue.get()
            indata = self.moving_average_filter(indata, 10)
            if self.is_noise:
                continue
            await self.send(indata.tobytes())

    def is_noise(self, data) -> bool:
        audio_data = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(np.square(audio_data)))
        return rms < self.NOISE_THRESHOLD

    async def _start_audio_stream(self):
        # 打开麦克风流
        with sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            callback=self.audio_callback,
        ):
            print("Recording...")
            # 持续录音直到手动中断
            while True:
                await asyncio.sleep(0.1)

    def moving_average_filter(self, audio_data, window_size):
        audio_data = audio_data.ravel()
        window = np.ones(window_size) / window_size
        filtered_data = convolve(audio_data, window, mode="same")
        return filtered_data

    def audio_callback(self, indata, frames, time, status):
        # 处理麦克风数据的回调函数
        if status:
            print(f"Warning: {status}, {frames} frames")
        # 将数据放入队列
        asyncio.run_coroutine_threadsafe(self.audio_queue.put(indata), self._loop)

    async def _error(self, e: Exception) -> None:
        """处理错误"""
        print(f"发生错误:{e}")
        # 如果你想要更详细的错误信息,可以使用traceback模块
        traceback_details = "".join(
            traceback.format_exception(type(e), e, e.__traceback__)
        )
        print(traceback_details)

    async def _connection_closed(self, connect: Connect) -> None:
        """连接被关闭"""
        await connect.close()


# 客户端
# 请注意,行模式(use_line)并不适合传输超过缓冲区大小的数据,如果在缓冲区没有读取到换行符,将会抛出异常
# 行模式使用的是StreamReader的readline方法
# 经过测试抛出的异常为`valueError: Separator is not found, and chunk exceed the limit`
# 被Connect捕获后为`ValueError: 行数据异常: Separator is not found, and chunk exceed the limit`
# 请注意,如果你的服务端使用了行模式,客户端也需要使用行模式,同理,如果服务端没有使用行模式,客户端也不需要使用行模式
# 客户端配置大部分情况下需要与服务端配置保持一致,未来可能会考虑自动配置(目前不支持)

# 这是一个简单的客户端实例
# MyClient(use_line=True,use_aes=False)

# 演示使用ssl
ssl_context = ssl.create_default_context()
# 设置具有前向保密的密码套件
ssl_context.set_ciphers(
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:"
    "ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256"
)
# 跳过证书验证和主机名验证,不建议在生产环境中使用
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


client = MyClient(ssl=ssl_context, use_line=True)
client.run()