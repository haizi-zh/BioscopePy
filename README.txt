?BioscopePy：

Haizi Zheng, August 20th, 2012

为D519设计的程序。其作用是：通过Guppy红外CCD对失踪小球进行成像。然后进行图像分析，得到球的中心位置。并采用纪伟提出的算法，分析球的纵向位置。另一方面，该程序可以控制MP-285平移台和压电平移台，分别操纵磁铁和样品台。

文件夹列表：

* Bioscope：主程序
* E7XX_swig：压电平移台E761的swig/Python接口
* FireGrab_swig：Guppy红外CCD的swig/Python接口
* mds：MP-285平移台的接口（通过RS232）