# car_dashboard_sim

WIP

### Final Goal是取代现在的车载仪表盘，自己自定义图形化界面显示速度/转速/油耗/里程/温度/故障灯等等，同时取代智能车机

用OBD-II接口直接读BSI里的数据，然后连一个RPi再外接一个小屏幕，直接把仪表盘DIY了，加点二次元风格（草），所有代码都自己写/vibe

ESP32-S3延迟低，但是customizable程度太低，用Android手机太慢，所以决定用RPi

供电使用保险盒+DC-DC稳压器

智能车机使用CarPlay+屏幕+车载音响加装蓝牙
