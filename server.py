from tcp_quick.server import Server, Connect
import traceback

# 如果你想要使用ssl,请取消下面的注释
from tcp_quick.cert_manager import CertManager
import os, ssl
import numpy as np
import sounddevice as sd


class MyServer(Server):
    SAMPLE_RATE = 44100  # 采样率
    CHANNELS = 1  # 声道数
    CHUNK_SIZE = 128  # 每次读取的数据块大小

    def __init__(self, *args, **kwargs):
        self.audio_stream = sd.OutputStream(
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            dtype=np.int16,
            blocksize=self.CHUNK_SIZE,
        )
        self.audio_stream.start()
        super().__init__(*args, **kwargs)

    async def _handle(self, connect: Connect) -> None:
        while True:
            data = await connect.recv(60)
            # 处理接收到的音频数据
            self.process_audio(data)

    def process_audio(self, data):
        # 播放接收到的音频数据
        audio_data = np.frombuffer(data, dtype=np.int16)
        self.audio_stream.write(audio_data)

    async def _error(self, addr, e: Exception) -> None:
        print(f"来自 {addr} 的连接出现错误: {e}")
        # 如果你想要更详细的错误信息,可以使用traceback模块
        traceback_details = "".join(
            traceback.format_exception(type(e), e, e.__traceback__)
        )
        print(traceback_details)

    async def _connection_closed(self, addr, connect: Connect) -> None:
        # 请在这里重写连接成功的连接被关闭时的处理(无论是正常关闭还是异常关闭),如果不重写,可以删除这个方法
        await super()._connection_closed(addr, connect)

# 演示使用ssl
private_key_path = "test/private.key"
certificate_path = "test/certificate.crt"
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
# 判断test目录是否存在
if not os.path.exists("test"):
    os.mkdir("test")
# 判断证书和私钥是否同时存在
if not os.path.exists(private_key_path) or not os.path.exists(certificate_path):
    # 生成证书和私钥
    private_key = CertManager.generate_private_key()
    certificate = CertManager.generate_certificate(
        private_key,
        CertManager.build_x509_name(common_name="localhost"),
        CertManager.build_x509_name(common_name="localhost"),
        valid_days=365,
        output_private_key_path=private_key_path,
        output_certificate_path=certificate_path,
    )
# 校验证书是否有效
certificate = CertManager.load_certificate_from_pem_file(certificate_path)
if not CertManager.check_certificate_validity(certificate):
    raise ValueError("证书已过期")
# 加载私钥
private_key = CertManager.load_private_key_from_pem_file(private_key_path)
# 校验证书和私钥是否匹配
if not CertManager.check_certificate_private_key_match(certificate, private_key):
    raise ValueError("证书和私钥不匹配")
# 加载证书
ssl_context.load_cert_chain(certificate_path, private_key_path)
# 如果你有CA证书,可以使用下面的方法加载CA证书
# ssl_context.load_verify_locations(cafile='this_is_ca.crt')
server = MyServer(listen_keywords=True, ssl=ssl_context, use_line=True)
server.run()