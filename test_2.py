import matplotlib.pyplot as plt
from astropy.io import fits
import numpy as np
import matplotlib.colors as colors

def fits_to_image(fits_path, output_path="output.png"):
    try:
        # 使用with语句确保文件安全打开
        with fits.open(r'd:\Users\李\Desktop\SDU\Study\太阳耀斑非热辐射研究\Flare\2024-08-08-X1.3\解压\20250227165050139698\hxi_q1\hly_fits') as hdul:
            hdul.info()
            data = hdul[0].data
            header = hdul[0].header

        # 预处理数据
        data = np.nan_to_num(data, nan=0.0, posinf=np.max(data[data != np.inf]))
        vmin = np.percentile(data, 5)
        vmax = np.percentile(data, 95)

        # 绘制图像
        plt.figure(figsize=(10, 8), dpi=150)
        ax = plt.gca()
        img = ax.imshow(
            data,
            cmap='hot',
            origin='lower',
            norm=colors.LogNorm(vmin=max(1e-10, vmin), vmax=vmax)
        )
        plt.colorbar(img, ax=ax, label="Intensity (DN)")
        plt.title(f"Solar Flare Observation\nDate: {header.get('DATE-OBS', 'Unknown')}")
        plt.xlabel("X Pixel")
        plt.ylabel("Y Pixel")
        plt.savefig(output_path, bbox_inches='tight', pad_inches=0.1)
        plt.close()
        print(f"Image saved to {output_path}")

    except PermissionError:
        print(f"权限拒绝！请检查：\n1. 文件是否被其他程序占用\n2. 路径是否有特殊字符\n3. 用户是否有读写权限")
        