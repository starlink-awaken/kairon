# kairon-voice

语音输入输出子系统，支持语音识别（STT）和语音合成（TTS）的多 provider 适配。

## 功能

- 语音输入：麦克风采集 + 语音识别
- 语音输出：文本转语音播放
- 多 provider 适配器（Whisper, Google TTS, 等）

## 安装

```bash
pip install kairon-voice
```

## 配置

通过环境变量或构造函数注入配置。详见 `src/kairon_voice/` 各模块文档。
