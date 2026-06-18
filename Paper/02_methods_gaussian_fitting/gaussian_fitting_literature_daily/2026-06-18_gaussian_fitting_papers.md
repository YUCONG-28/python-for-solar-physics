# 2026-06-18 Gaussian fitting 文献更新

### Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm

- 年份：2026
- 期刊/来源：arXiv preprint
- 相关性：A
- 主题标签：beam / PSF; frequency drift rate; Gaussian fitting / radio source centroid; LOFAR; Newkirk density model / frequency drift / source motion; radio source morphology; solar radio fine structures; solar radio imaging instruments; solar radio spikes; source size; spikes topping type III / type III burst
- 简述：LOFAR 30-40 MHz 噪声暴精细结构论文，明确使用 CLEAN 后图像的 2D elliptical Gaussian 拟合，输出 centroid、FWHM major/minor、面积和不确定度，是当前 Gaussian source-position / source-size 方法库的新增核心参考。
- 对当前项目的价值：直接补强 DART / DRAT 图像中 Gaussian center、FWHM、beam/PSF、centroid uncertainty 和多源 centroid jump 的质量控制方案。
- 链接：arXiv: 2605.31450
- 该论文如何定义 radio source center：Source centroid locations are the x0/y0 positions from the 2D elliptical Gaussian fits to clean LOFAR maps and are tracked over time/frequency.
- 是否使用 2D Gaussian / elliptical Gaussian：Clean maps are fitted with a 2D elliptical Gaussian; fitted parameters include amplitude, x0/y0, sigma_x/y and rotation angle. Frequency-time drift profiles use Gaussian + background + linear continuum.
- 是否讨论 FWHM / source size：FWHM major/minor axes and FWHM area are derived from Gaussian widths; the paper distinguishes cleaned/deconvolved continuum sizes from beam-convolved fine-structure sizes.
- 是否处理 beam deconvolution：Dirty maps are CLEANed; an effective PSF is estimated from Tau A observations and translated to the solar position; frequency-dependent ionospheric refraction correction is applied.
- 是否讨论 centroid uncertainty：Centroid uncertainties follow Condon-style formulae; flux/noise is estimated from faint beams; drift-rate uncertainty uses Gaussian peak-frequency errors or manual slope bounds for low-contrast S bursts.
- 是否适合当前 DART / DRAT 射电源图像：极高，适合直接借鉴到当前 DART / DRAT 的 Gaussian center、FWHM、residual、centroid uncertainty 和 multi-peak 诊断输出。

### Imaging spectroscopy reveals spike-like repeating radio burst pairs in the solar corona

- 年份：2026
- 期刊/来源：Nature Communications
- 相关性：A
- 主题标签：frequency drift rate; Gaussian fitting / radio source centroid; imaging spectroscopy; Newkirk density model / frequency drift / source motion; radio source centroid; spike-like repeating burst pairs; spikes topping type III / type III burst; type III radio burst
- 简述：已从 arXiv 转为 Nature Communications 正式论文；把 spike-like burst pairs、成像频谱、源区位移和频率漂移串到一起，是当前主题与方法链条都高度贴近的新论文。
- 对当前项目的价值：同时支撑 fine structure 物理解释、源区运动分析和后续 Gaussian center 讨论。
- 链接：DOI: 10.1038/s41467-026-74137-2
- 该论文如何定义 radio source center：基于成像频谱的源位置与位移度量。
- 是否使用 2D Gaussian / elliptical Gaussian：需要全文核对具体成像拟合模型；摘要已明确使用成像频谱与源位移分析。
- 是否讨论 FWHM / source size：摘要层面未给出显式 FWHM 公式，全文需补充。
- 是否处理 beam deconvolution：需全文核对 beam / scattering 处理细节。
- 是否讨论 centroid uncertainty：需全文核对位置与位移误差定义。
- 是否适合当前 DART / DRAT 射电源图像：可直接参考其成像频谱与源位移解释框架。

### Magnetic Field Geometry and Anisotropic Scattering Effects on Solar Radio Burst Observations

- 年份：2025
- 期刊/来源：The Astrophysical Journal
- 相关性：A
- 主题标签：anisotropic scattering; frequency drift rate; Gaussian fitting / radio source centroid; magnetic field geometry; Newkirk density model / frequency drift / source motion; radio source morphology; solar radio fine structures; solar radio imaging instruments; source motion; source position; spikes topping type III / type III burst
- 简述：该文说明磁场几何和各向异性散射会改变 fine-structure 的表观源区形态、源区运动、源区分裂和频漂率，是解释 Gaussian center 与 contour center 偏差的重要物理背景。
- 对当前项目的价值：为 Gaussian 椭圆方向、multi-peak flag、source trajectory 和 drift-rate 速度解释提供直接的物理边界。
- 链接：DOI: 10.3847/1538-4357/ad969c
- 该论文如何定义 radio source center：apparent source position may move along magnetic-field geometry rather than density-gradient direction.
- 是否使用 2D Gaussian / elliptical Gaussian：不提供拟合公式；用于解释为什么单源 Gaussian 椭圆和中心可能只是传播后的表观结果。
- 是否讨论 FWHM / source size：source morphology and apparent size are modified by anisotropic scattering and can split into multiple apparent components.
- 是否处理 beam deconvolution：强调 scattering / propagation 是 beam 之外的关键表观扩展与分裂来源。
- 是否讨论 centroid uncertainty：把磁场几何、散射各向异性和 source bifurcation 作为 centroid 系统误差来源。
- 是否适合当前 DART / DRAT 射电源图像：高，适合解释 DART / DRAT 图像中低频源区拉长、偏心、多峰和 trajectory 异常。

### Sizes and Shapes of Solar Type III Radio Burst Sources in LOFAR Tied-Array Imaging and the Role of Scattering

- 年份：2021
- 期刊/来源：Astronomy & Astrophysics / arXiv
- 相关性：A
- 主题标签：Gaussian fitting / radio source centroid; LOFAR; scattering; solar radio imaging instruments; source morphology; source size; spikes topping type III / type III burst; type III radio burst
- 简述：专门讨论 III 型暴源区尺寸、形状和散射效应，非常适合作为 FWHM、形态和 apparent size 的方法库核心文献。
- 对当前项目的价值：有助于解释为什么低频图像上的大 FWHM 不一定等于真实源区扩展。
- 链接：arXiv: 2011.13735
- 该论文如何定义 radio source center：以多频成像源位移和形状演化共同约束中心位置。
- 是否使用 2D Gaussian / elliptical Gaussian：围绕源区尺寸和形状拟合展开，适合作为 elliptical Gaussian / shape fitting 参考。
- 是否讨论 FWHM / source size：重点关注表观 source size、shape 和频率依赖性。
- 是否处理 beam deconvolution：核心强调 scattering，使去卷积后的真实尺寸解释仍需谨慎。
- 是否讨论 centroid uncertainty：应结合 source shape 与 scattering 不确定性联合评估。
- 是否适合当前 DART / DRAT 射电源图像：高，适合指导 source size / morphology 的论文写法和质量控制。

### Sub-second Time Evolution of Type III Solar Radio Burst Sources at Fundamental and Harmonic Frequencies

- 年份：2020
- 期刊/来源：The Astrophysical Journal
- 相关性：A
- 主题标签：anisotropic scattering; fundamental emission; Gaussian fitting / radio source centroid; harmonic emission; radio source centroid; solar radio imaging instruments; source size; spikes topping type III / type III burst; type III radio burst; type IIIb
- 简述：该文把 III/IIIb 源区 sub-second centroid、source size 和 fundamental/harmonic 差异与各向异性散射模拟联系起来，是解释低频源区中心漂移和 apparent size 的关键文献。
- 对当前项目的价值：支撑当前项目在低频弱源或 early frames 中谨慎解释 Gaussian center 漂移和 FWHM 变化。
- 链接：DOI: 10.3847/1538-4357/abc24e
- 该论文如何定义 radio source center：使用窄频成像得到的 centroid locations 作为表观源位置，并与传播模拟输出比较。
- 是否使用 2D Gaussian / elliptical Gaussian：不以 Gaussian 公式为主，重点是观测 centroid locations 与 source sizes 的时序解释。
- 是否讨论 FWHM / source size：比较 fundamental 与 harmonic apparent source sizes 及其 sub-second 演化。
- 是否处理 beam deconvolution：重点讨论各向异性散射造成的表观位置和尺寸变化；真实源区大小解释需保守。
- 是否讨论 centroid uncertainty：将传播散射作为系统误差来源，不能只用拟合协方差衡量 centroid 可靠性。
- 是否适合当前 DART / DRAT 射电源图像：高，适合解释低频源区的 centroid drift、FWHM 增大和速度估计偏差。

### Frequency-Distance Structure of Solar Radio Sources Observed by LOFAR

- 年份：2019
- 期刊/来源：The Astrophysical Journal
- 相关性：A
- 主题标签：elliptical Gaussian; frequency-distance relation; Gaussian fitting / radio source centroid; LOFAR; Newkirk density model; Newkirk density model / frequency drift / source motion; radio source centroid; scattering; solar radio imaging instruments
- 简述：LOFAR 30-50 MHz 频率-距离结构论文，明确比较最大亮度点、阈值质心和 2D 椭圆 Gaussian 拟合三种源位置方法，并指出 Newkirk 等密度模型与表观位置可能明显不一致。
- 对当前项目的价值：直接支持 Gaussian center 与 contour/阈值中心对比，并提醒 Newkirk 高度不能直接等同表观射电源位置。
- 链接：DOI: 10.3847/1538-4357/ab03d8
- 该论文如何定义 radio source center：source position 可由 intensity maximum、0.5 peak 阈值 center-of-mass 或 2D elliptical Gaussian center 得到，三者接近时说明源形态较对称。
- 是否使用 2D Gaussian / elliptical Gaussian：使用 2D elliptical Gaussian fitting，并与最大亮度点和半峰值阈值中心方法交叉比较。
- 是否讨论 FWHM / source size：源形态近似椭圆；重点在位置-频率关系而非单独 FWHM 统计。
- 是否处理 beam deconvolution：记录 LOFAR beam 尺度，并把电离层折射、散射和密度模型偏差作为表观位置误差来源。
- 是否讨论 centroid uncertainty：使用 Tau A 多频观测估计 centroid 误差和电离层折射修正，适合当前项目借鉴外部校准思路。
- 是否适合当前 DART / DRAT 射电源图像：极高，尤其适合建立 Gaussian center 与 contour center / intensity-weighted center 的可靠性验证。

### On the Source Position and Duration of a Solar Type III Radio Burst Observed by LOFAR

- 年份：2019
- 期刊/来源：The Astrophysical Journal
- 相关性：A
- 主题标签：frequency drift rate; Gaussian fitting; Gaussian fitting / radio source centroid; LOFAR; Newkirk density model / frequency drift / source motion; radio source centroid; solar radio imaging instruments; spikes topping type III / type III burst; type III radio burst
- 简述：LOFAR 成像频谱直接讨论 III 型暴的表观源位置、持续时间和传播效应，是 radio centroid 与 source motion 的关键方法论文。
- 对当前项目的价值：可直接借鉴 centroid/trajectory 分析思路，并提醒传播效应会扭曲源区解释。
- 链接：DOI: 10.3847/1538-4357/ab45f5
- 该论文如何定义 radio source center：以成像频谱得到的源位置 / centroid 追踪 burst 在不同频率与时刻的表观位置。
- 是否使用 2D Gaussian / elliptical Gaussian：文摘与相关介绍指向椭圆源形拟合；正式引用前建议在全文核对参数化形式。
- 是否讨论 FWHM / source size：讨论源持续时间与表观尺寸，适合作为 FWHM / size 的方法背景。
- 是否处理 beam deconvolution：强调传播与散射影响表观位置和尺寸，beam 解释需谨慎。
- 是否讨论 centroid uncertainty：可结合其位置变化和传播讨论，转化为 centroid 可靠性约束。
- 是否适合当前 DART / DRAT 射电源图像：高，适合借鉴源中心轨迹、持续时间和传播偏差解释。

### The apparent positions of solar radio sources observed by the Low Frequency Array

- 年份：2017
- 期刊/来源：Scientific Reports
- 相关性：A
- 主题标签：beam effects; elliptical Gaussian; Gaussian fitting / radio source centroid; LOFAR; radio source centroid; solar radio imaging instruments; source size
- 简述：LOFAR 低频太阳射电源位置与面积的经典方法文献，明确涉及 elliptical Gaussian、源区大小和散射/表观位置偏差。
- 对当前项目的价值：可直接借鉴 centroid、FWHM/area 和 apparent size 的写法，是 DART / DRAT 成像拟合最关键的参考之一。
- 链接：DOI: 10.1038/s41598-017-14072-y
- 该论文如何定义 radio source center：椭圆 Gaussian 的中心位置作为 radio source centroid / source position。
- 是否使用 2D Gaussian / elliptical Gaussian：At each observing frequency the source position and area are fitted with an elliptical Gaussian.
- 是否讨论 FWHM / source size：由椭圆 Gaussian 的 major / minor axis 或面积表征表观 source size。
- 是否处理 beam deconvolution：重点讨论 scattering 对 apparent position 和 apparent size 的影响；真实尺寸解释需谨慎。
- 是否讨论 centroid uncertainty：可结合频率依赖的表观位移和散射讨论 centroid uncertainty。
- 是否适合当前 DART / DRAT 射电源图像：极高，可直接迁移到当前的 centroid / size / apparent source size 叙述框架。

### A decade of solar Type III radio bursts observed by the Nancay Radioheliograph 1998-2008

- 年份：2013
- 期刊/来源：The Astrophysical Journal
- 相关性：A
- 主题标签：2D elliptical Gaussian; beam deconvolution; FWHM; Gaussian fitting / radio source centroid; Nancay Radioheliograph; solar radio imaging instruments; source position; source size; spikes topping type III / type III burst; type III radio burst
- 简述：NRH 近万例 III 型暴统计论文，明确使用 2D elliptical Gaussian 拟合源区，给出 observed/deconvolved FWHM、主轴/次轴和 beam 去卷积思路，是 Gaussian source-size 方法库核心文献。
- 对当前项目的价值：直接支撑当前项目把 Gaussian 椭圆参数写成 observed apparent size，并在 beam 信息可靠时再讨论 deconvolved size。
- 链接：DOI: 10.1088/0004-637X/762/1/60
- 该论文如何定义 radio source center：Gaussian source fit provides the apparent source position on NRH maps; statistical source positions are then analyzed over solar cycle.
- 是否使用 2D Gaussian / elliptical Gaussian：Radio sources were fitted with 2D elliptical Gaussians to obtain semi-major/minor widths and tilt angle.
- 是否讨论 FWHM / source size：sigma major/minor are converted to FWHM with 2.355, and rms FWHM is used for size statistics.
- 是否处理 beam deconvolution：Assumes observed source, interferometer beam and intrinsic source are elliptical Gaussians; derives deconvolved true source size when beam is known.
- 是否讨论 centroid uncertainty：Beamwidth, temporal averaging, alias ambiguity and multiple sources are treated as important limitations.
- 是否适合当前 DART / DRAT 射电源图像：极高，适合定义 FWHM_major/minor、beam deconvolution 和 overlarge_fwhm flag 的论文写法。

### Electron Beam Propagation and Radio-Wave Scattering in the Inner Heliosphere using Five Spacecraft

- 年份：2025
- 期刊/来源：Astronomy & Astrophysics
- 相关性：B
- 主题标签：electron beam; frequency drift rate; Newkirk density model / frequency drift / source motion; scattering; source motion; spikes topping type III / type III burst; type III radio burst
- 简述：多航天器结果强调传播和散射会扭曲 III 型暴的频漂与定位，非常适合约束 Newkirk 和速度解释的边界。
- 对当前项目的价值：提醒不能把 Newkirk 高度、Gaussian center 和电子束真实速度简单等同。
- 链接：待补充
- 该论文如何定义 radio source center：更侧重传播偏差，不以单一 centroid 拟合为主。
- 是否使用 2D Gaussian / elliptical Gaussian：
- 是否讨论 FWHM / source size：
- 是否处理 beam deconvolution：突出 scattering 对表观位置和频漂的影响。
- 是否讨论 centroid uncertainty：传播路径和散射本身构成系统误差来源。
- 是否适合当前 DART / DRAT 射电源图像：中高，适合写入误差和物理解释边界。

### A Review of Recent Solar Type III Imaging Spectroscopy

- 年份：2020
- 期刊/来源：Frontiers in Astronomy and Space Sciences
- 相关性：B
- 主题标签：frequency drift rate; imaging spectroscopy; Newkirk density model / frequency drift / source motion; review; source region; spikes topping type III / type III burst; type III radio burst
- 简述：III 型暴成像频谱的综述入口，适合统筹源区、传播、散射和精细结构的整体框架。
- 对当前项目的价值：适合作为文献综述的总入口，再向 Gaussian fitting、AIA 联合分析和 drift-rate 细分展开。
- 链接：DOI: 10.3389/fspas.2020.00056
- 该论文如何定义 radio source center：总结 source region / centroid 的观测局限。
- 是否使用 2D Gaussian / elliptical Gaussian：综述性质，不提供单一拟合公式。
- 是否讨论 FWHM / source size：总结 apparent size 与 scattering 问题。
- 是否处理 beam deconvolution：总结 beam / scattering / propagation 的综合影响。
- 是否讨论 centroid uncertainty：适合作为 centroid uncertainty 的背景综述。
- 是否适合当前 DART / DRAT 射电源图像：适合搭建整个论文的方法与背景框架。

### Type III Solar Radio Burst Source Region Splitting Due to a Quasi-Separatrix Layer

- 年份：2017
- 期刊/来源：Nature Communications
- 相关性：B
- 主题标签：Gaussian fitting / radio source centroid; magnetic topology; solar radio imaging instruments; source morphology; source region splitting; spikes topping type III / type III burst; type III radio burst
- 简述：源区分裂说明单峰拟合并不总是足够，特别适合提醒当前项目在多峰或磁拓扑复杂场景下不要过度解读单个 Gaussian center。
- 对当前项目的价值：可作为多峰源与单源 Gaussian 失效情形的关键警示文献。
- 链接：待补充
- 该论文如何定义 radio source center：多源结构下单个 centroid 可能不再具有唯一物理意义。
- 是否使用 2D Gaussian / elliptical Gaussian：该文更强调形态分裂，不应默认单源 Gaussian 足够。
- 是否讨论 FWHM / source size：形态分裂比单一 FWHM 更关键。
- 是否处理 beam deconvolution：重点不在 beam 去卷积，而在磁拓扑导致的真实多源形态。
- 是否讨论 centroid uncertainty：应把多峰结构本身视为 centroid 不确定性的来源。
- 是否适合当前 DART / DRAT 射电源图像：中高，尤其适合低频多峰事件的质量控制。
