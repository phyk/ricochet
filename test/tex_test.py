import matplotlib.pyplot as plt
import numpy as np

if __name__ == '__main__':
    t = np.arange(0.0, 1.0 + 0.01, 0.1)
    s = np.cos(4 * np.pi * t) + 2

    plt.rc('text', usetex=True)
    plt.rc('font', family='serif')
    plt.plot(t, s)

    plt.xlabel(r'\textbf{time} (s)')
    plt.ylabel(r'\textit{voltage} (mV)', fontsize=16)
    plt.title(r'\TeX\ is Number '
              r'$\displaystyle\sum_{n=low}^\infty\frac{-e^{i\pi}}{0^n}$!',
              fontsize=16, color='gray')
    # Make room for the ridiculously large title.
    plt.subplots_adjust(top=0.8)

    plt.savefig('tex_demo')
    plt.show()
