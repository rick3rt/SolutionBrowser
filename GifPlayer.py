from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy, QApplication, QGridLayout, QFrame, QShortcut
from PyQt5.QtGui import QMovie, QKeySequence
from PyQt5.QtCore import QDir, Qt, QSize, QByteArray


class GifPlayer(QWidget):
    def __init__(self, hsize, vsize, parent=None):
        super(GifPlayer, self).__init__(parent)

        # set size and title
        self.resize(hsize, vsize)
        self.setWindowTitle('Gif Viewer')

        # create frame
        # self.layout = QGridLayout()
        self.frame = QFrame(self)
        # self.frame.setLayout(self.layout)

        # label for movie
        self.gif_label = QLabel(self.frame)
        self.gif_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.gif_label.setAlignment(Qt.AlignCenter)

        # add stuff to layout
        # self.layout.addWidget(self.gif_label, 0, 0, 1, 1)
        # self.layout.setContentsMargins(1, 1, 1, 1)

        # create actions / shortcuts
        self.createActions()

        # Load the file into a QMovie
        # size = self.movie.scaledSize()
        # self.setGeometry(200, 200, size.width(), size.height())
        # self.setWindowTitle(title)

    def load_gif(self, fileName):
        self.gif = QMovie(fileName, QByteArray(), self.gif_label)

        self.gif.setCacheMode(QMovie.CacheAll)
        self.gif.setSpeed(100)
        self.gif_label.setMovie(self.gif)

        # gif_size = self.gif.scaledSize()
        # print(gif_size)

        # self.gif_asp_ratio =

        # gif_size = self.gif.scaledSize()
        # self.gif_label.setFixedHeight(gif_size.height())
        # self.gif_label.setFixedWidth(gif_size.width())

        self.gif.start()

    # def fix_size(self):
    #     screen_size = self.geometry()
    #     gif_size = self.gif.scaledSize()

    #     print(screen_size)
    #     print(gif_size)

    def createActions(self):
        self.close_window_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.close_window_shortcut.activated.connect(self.close)

    # def resizeEvent(self, event):
    #     self.gif.setScaledSize(QSize(1000, 1000))
    #     self.gif_label.setFixedSize(1000, 1000)
    #     self.fix_size()


if __name__ == "__main__":
    import sys
    gif = "test.gif"
    app = QApplication(sys.argv)
    player = GifPlayer(800, 600)
    player.show()
    player.load_gif('test.gif')
    player.show()

    sys.exit(app.exec_())
