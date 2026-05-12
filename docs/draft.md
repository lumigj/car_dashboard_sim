# car_dashboard_sim

WIP

### Final Goal是取代现在的车载仪表盘，自己自定义图形化界面显示速度/转速/油耗/里程/温度/故障灯等等，同时取代智能车机

用OBD-II接口直接读BSI里的数据，然后连一个RPi再外接一个小屏幕，直接把仪表盘DIY了，加点二次元风格（草），所有代码都自己写/vibe

ESP32-S3延迟低，但是customizable程度太低，用Android手机太慢，所以决定用RPi

供电使用保险盒+DC-DC稳压器

智能车机使用CarPlay+屏幕+车载音响加装蓝牙

行车电脑 -> 
仪表盘 （速度 转速 水温 剩余油量 里程）
车机 （时间日期 里程 油耗 气温）

### 车机：听歌 看导航 凡是不涉及读取汽车数据的 都可以简单在这里实现
AirPlay + a.蓝牙转接车载音响 + 

a. 手机蓝牙 + (1)点烟器converter（蓝牙信号 转换为广播频率 比如106.3）-> radio广播频率 + 车载音响

### 仪表盘
行车电脑（BSI）-> OBD-II 包含仪表盘 （速度 转速 水温 剩余油量 里程）数据
买一个OBD reader / OBD scanner = （ELM327是硬件名称）
1. UART TTL线 RX/TX/GND PIN口
2. 蓝牙 -> 安卓/IOS 上面的软件 对应：手机
3. BLE = bluetooth low energy -> 支持蓝牙的嵌入式 比如高配RPi Arduino ESP32
4. USB FT232RL(TTL->USB)

先找1 4我买了作为替代品

1. 手机 x
2. ESP32-S3 可视化界面难开发 只能用仿C++的Arduino IDE x
3. Arduino可视化界面难开发 只能用仿C++的Arduino IDE x
4. RPi 延迟可以接受 功能多

用4 我买了

屏幕 用PyQt5做可视化 再用屏幕直接连接RPi

供电：车保险盒供电（点烟器）(1) -> DC-DC稳压器 -> 功率显示 数显 数据线-> RPi

你做的部分：
用PyQt5做可视化 发到RPi上
UI设计（数字仪表盘）
mockup data 给我留API！ CSV datasheet column 秒数：时速 毫秒数：转速 分钟：油量
运行一遍用PyQt5绘制出来