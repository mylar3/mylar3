"""Some utilities for the GUI"""

#import StringIO

#from PIL import Image

from comictaggerlib.settings import ComicTaggerSettings


try:
    from PyQt5 import QtGui
    qt_available = True
except ImportError:
    qt_available = False

if qt_available:

    def reduceWidgetFontSize(widget, delta=2):
        f = widget.font()
        if f.pointSize() > 10:
            f.setPointSize(f.pointSize() - delta)
        widget.setFont(f)

    def centerWindowOnScreen(window):
        """Center the window on screen.

        This implementation will handle the window
        being resized or the screen resolution changing.
        """
        # Get the current screens' dimensions...
        screen = QtGui.QDesktopWidget().screenGeometry()
        # ... and get this windows' dimensions
        mysize = window.geometry()
        # The horizontal position is calculated as screen width - window width
        # / 2
        hpos = (screen.width() - window.width()) / 2
        # And vertical position the same, but with the height dimensions
        vpos = (screen.height() - window.height()) / 2
        # And the move call repositions the window
        window.move(hpos, vpos)

    def centerWindowOnParent(window):

        top_level = window
        while top_level.parent() is not None:
            top_level = top_level.parent()

        # Get the current screens' dimensions...
        main_window_size = top_level.geometry()
        # ... and get this windows' dimensions
        mysize = window.geometry()
        # The horizontal position is calculated as screen width - window width
        # /2
        hpos = (main_window_size.width() - window.width()) / 2
        # And vertical position the same, but with the height dimensions
        vpos = (main_window_size.height() - window.height()) / 2
        # And the move call repositions the window
        window.move(
            hpos +
            main_window_size.left(),
            vpos +
            main_window_size.top())

    try:
        from PIL import Image
        from PIL import WebPImagePlugin
        import io
        pil_available = True
    except ImportError:
        pil_available = False

    def getQImageFromData(image_data):
        img = QtGui.QImage()
        success = img.loadFromData(image_data)
        if not success:
            try:
                if pil_available:
                    #  Qt doesn't understand the format, but maybe PIL does
                    # so try to convert the image data to uncompressed tiff
                    # format
                    im = Image.open(io.StringIO(image_data))
                    output = io.StringIO()
                    im.save(output, format="PNG")
                    success = img.loadFromData(output.getvalue())
            except Exception as e:
                pass
        # if still nothing, go with default image
        if not success:
            img.load(ComicTaggerSettings.getGraphic('nocover.png'))
        return img
