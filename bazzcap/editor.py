
import os
import math
from enum import Enum ,auto

from PyQt6 .QtWidgets import (
QMainWindow ,QGraphicsScene ,QGraphicsView ,QGraphicsItem ,
QGraphicsPixmapItem ,QGraphicsRectItem ,QGraphicsEllipseItem ,
QGraphicsLineItem ,QGraphicsPathItem ,QGraphicsTextItem ,
QGraphicsItemGroup ,QToolBar ,QStatusBar ,QWidget ,
QHBoxLayout ,QVBoxLayout ,QLabel ,QSpinBox ,QColorDialog ,
QPushButton ,QSizePolicy ,QToolButton ,QFileDialog ,
QApplication ,QGraphicsDropShadowEffect ,QMessageBox ,
)
from PyQt6 .QtCore import (
Qt ,QRectF ,QPointF ,QLineF ,QSizeF ,pyqtSignal ,QEvent ,QSize ,
)
from PyQt6 .QtGui import (
QPixmap ,QImage ,QPen ,QBrush ,QColor ,QPainter ,QFont ,
QAction ,QIcon ,QPainterPath ,QPolygonF ,QKeySequence ,
QTransform ,QCursor ,
)

class Tool (Enum ):
    SELECT =auto ()
    RECTANGLE =auto ()
    ELLIPSE =auto ()
    LINE =auto ()
    ARROW =auto ()
    FREEHAND =auto ()
    TEXT =auto ()
    BLUR =auto ()
    HIGHLIGHT =auto ()
    STEP_MARKER =auto ()
    CROP =auto ()

class ArrowItem (QGraphicsLineItem ):

    def __init__ (self ,line :QLineF ,pen :QPen ,parent =None ):
        super ().__init__ (line ,parent )
        self .setPen (pen )
        self ._arrow_size =max (12 ,pen .widthF ()*3 )

    def paint (self ,painter ,option ,widget =None ):
        painter .setRenderHint (QPainter .RenderHint .Antialiasing )
        pen =self .pen ()
        painter .setPen (pen )

        line =self .line ()
        painter .drawLine (line )

        angle =math .atan2 (
        -(line .y2 ()-line .y1 ()),
        line .x2 ()-line .x1 (),
        )

        arrow_p1 =QPointF (
        line .x2 ()-self ._arrow_size *math .cos (angle -math .pi /6 ),
        line .y2 ()+self ._arrow_size *math .sin (angle -math .pi /6 ),
        )
        arrow_p2 =QPointF (
        line .x2 ()-self ._arrow_size *math .cos (angle +math .pi /6 ),
        line .y2 ()+self ._arrow_size *math .sin (angle +math .pi /6 ),
        )

        arrow_head =QPolygonF ([line .p2 (),arrow_p1 ,arrow_p2 ])
        painter .setBrush (QBrush (pen .color ()))
        painter .drawPolygon (arrow_head )

class BlurItem (QGraphicsRectItem ):

    def __init__ (self ,rect :QRectF ,source_pixmap :QPixmap ,blur_radius :int =15 ,parent =None ):
        super ().__init__ (rect ,parent )
        self ._source =source_pixmap
        self ._blur_radius =blur_radius
        self ._update_blur ()
        self .setPen (QPen (Qt .GlobalColor .transparent ))

    def _update_blur (self ):
        rect =self .rect ().toRect ()
        if rect .width ()<1 or rect .height ()<1 :
            self ._blurred =None
            return

        src_rect =rect .intersected (self ._source .rect ())
        if src_rect .isEmpty ():
            self ._blurred =None
            return

        region =self ._source .copy (src_rect )
        img =region .toImage ()

        from PyQt6 .QtCore import QRect
        blurred_img =self ._box_blur (img ,self ._blur_radius )
        self ._blurred =QPixmap .fromImage (blurred_img )
        self ._src_rect =src_rect

    @staticmethod
    def _box_blur (image :QImage ,radius :int )->QImage :
        if radius <1 :
            return image
        w ,h =image .width (),image .height ()
        block =max (2 ,radius )
        small =image .scaled (
        max (1 ,w //block ),max (1 ,h //block ),
        Qt .AspectRatioMode .IgnoreAspectRatio ,
        Qt .TransformationMode .SmoothTransformation ,
        )
        return small .scaled (
        w ,h ,
        Qt .AspectRatioMode .IgnoreAspectRatio ,
        Qt .TransformationMode .SmoothTransformation ,
        )

    def paint (self ,painter ,option ,widget =None ):
        if self ._blurred and hasattr (self ,'_src_rect'):
            painter .drawPixmap (self .rect ().toRect (),self ._blurred )
        else :
            painter .setBrush (QBrush (QColor (128 ,128 ,128 ,180 )))
            painter .setPen (Qt .PenStyle .NoPen )
            painter .drawRect (self .rect ())

class HighlightItem (QGraphicsRectItem ):

    def __init__ (self ,rect :QRectF ,color :QColor ,opacity :float =0.35 ,parent =None ):
        super ().__init__ (rect ,parent )
        c =QColor (color )
        c .setAlphaF (opacity )
        self .setBrush (QBrush (c ))
        self .setPen (QPen (Qt .GlobalColor .transparent ))

class StepMarkerItem (QGraphicsItemGroup ):

    _counter =0

    @classmethod
    def reset_counter (cls ):
        cls ._counter =0

    @classmethod
    def next_number (cls ):
        cls ._counter +=1
        return cls ._counter

    def __init__ (self ,center :QPointF ,color :QColor ,number :int =None ,parent =None ):
        super ().__init__ (parent )
        if number is None :
            number =StepMarkerItem .next_number ()
        self ._number =number

        radius =16
        ellipse =QGraphicsEllipseItem (
        center .x ()-radius ,center .y ()-radius ,
        radius *2 ,radius *2 ,
        )
        ellipse .setBrush (QBrush (color ))
        ellipse .setPen (QPen (QColor (255 ,255 ,255 ),2 ))

        text =QGraphicsTextItem (str (number ))
        font =QFont ("Arial",12 ,QFont .Weight .Bold )
        text .setFont (font )
        text .setDefaultTextColor (QColor (255 ,255 ,255 ))
        br =text .boundingRect ()
        text .setPos (
        center .x ()-br .width ()/2 ,
        center .y ()-br .height ()/2 ,
        )

        self .addToGroup (ellipse )
        self .addToGroup (text )

class UndoStack :

    def __init__ (self ,scene :QGraphicsScene ):
        self ._scene =scene
        self ._undo_stack :list [QGraphicsItem ]=[]
        self ._redo_stack :list [QGraphicsItem ]=[]

    def push (self ,item :QGraphicsItem ):
        self ._scene .addItem (item )
        self ._undo_stack .append (item )
        self ._redo_stack .clear ()

    def undo (self ):
        if self ._undo_stack :
            item =self ._undo_stack .pop ()
            self ._scene .removeItem (item )
            self ._redo_stack .append (item )

    def redo (self ):
        if self ._redo_stack :
            item =self ._redo_stack .pop ()
            self ._scene .addItem (item )
            self ._undo_stack .append (item )

    def can_undo (self ):
        return bool (self ._undo_stack )

    def can_redo (self ):
        return bool (self ._redo_stack )

    @property
    def items (self ):
        return list (self ._undo_stack )

class EditorCanvas (QGraphicsView ):

    tool_changed =pyqtSignal (Tool )

    def __init__ (self ,pixmap :QPixmap ,config ,parent =None ):
        super ().__init__ (parent )
        self ._config =config
        self ._source_pixmap =pixmap

        self ._scene =QGraphicsScene (self )
        self ._scene .setSceneRect (QRectF (pixmap .rect ()))
        self .setScene (self ._scene )

        self ._bg_item =QGraphicsPixmapItem (pixmap )
        self ._bg_item .setZValue (-1000 )
        self ._scene .addItem (self ._bg_item )

        self ._tool =Tool .SELECT
        self ._color =QColor (config .get ("editor.default_color","#FF0000"))
        self ._line_width =config .get ("editor.default_line_width",3 )
        self ._font_size =config .get ("editor.default_font_size",16 )
        self ._blur_radius =config .get ("editor.blur_radius",15 )
        self ._highlight_opacity =config .get ("editor.highlight_opacity",0.35 )
        self ._undo_stack =UndoStack (self ._scene )

        self ._drawing =False
        self ._start_pos =QPointF ()
        self ._current_item =None
        self ._freehand_path =None

        self ._crop_rect =None
        self ._crop_item =None

        self .setRenderHint (QPainter .RenderHint .Antialiasing )
        self .setRenderHint (QPainter .RenderHint .SmoothPixmapTransform )
        self .setDragMode (QGraphicsView .DragMode .NoDrag )
        self .setTransformationAnchor (QGraphicsView .ViewportAnchor .AnchorUnderMouse )
        self .setResizeAnchor (QGraphicsView .ViewportAnchor .AnchorUnderMouse )

        self .fitInView (self ._bg_item ,Qt .AspectRatioMode .KeepAspectRatio )

    @property
    def tool (self ):
        return self ._tool

    @tool .setter
    def tool (self ,t :Tool ):
        self ._tool =t
        if t ==Tool .SELECT :
            self .setCursor (Qt .CursorShape .ArrowCursor )
        elif t ==Tool .TEXT :
            self .setCursor (Qt .CursorShape .IBeamCursor )
        elif t ==Tool .CROP :
            self .setCursor (Qt .CursorShape .CrossCursor )
        else :
            self .setCursor (Qt .CursorShape .CrossCursor )
        self .tool_changed .emit (t )

    @property
    def color (self ):
        return self ._color

    @color .setter
    def color (self ,c :QColor ):
        self ._color =c

    @property
    def line_width (self ):
        return self ._line_width

    @line_width .setter
    def line_width (self ,w :int ):
        self ._line_width =w

    @property
    def font_size (self ):
        return self ._font_size

    @font_size .setter
    def font_size (self ,s :int ):
        self ._font_size =s

    def _pen (self ):
        return QPen (self ._color ,self ._line_width ,
        Qt .PenStyle .SolidLine ,Qt .PenCapStyle .RoundCap ,
        Qt .PenJoinStyle .RoundJoin )

    def mousePressEvent (self ,event ):
        if event .button ()!=Qt .MouseButton .LeftButton :
            return super ().mousePressEvent (event )

        pos =self .mapToScene (event .pos ())
        self ._start_pos =pos
        self ._drawing =True

        if self ._tool ==Tool .SELECT :
            super ().mousePressEvent (event )
            return

        if self ._tool ==Tool .FREEHAND :
            self ._freehand_path =QPainterPath ()
            self ._freehand_path .moveTo (pos )
            self ._current_item =QGraphicsPathItem (self ._freehand_path )
            self ._current_item .setPen (self ._pen ())
            self ._scene .addItem (self ._current_item )

        elif self ._tool ==Tool .TEXT :
            text_item =QGraphicsTextItem ("Text")
            text_item .setDefaultTextColor (self ._color )
            text_item .setFont (QFont ("Sans",self ._font_size ))
            text_item .setPos (pos )
            text_item .setTextInteractionFlags (
            Qt .TextInteractionFlag .TextEditorInteraction
            )
            text_item .setFlags (
            QGraphicsItem .GraphicsItemFlag .ItemIsMovable |
            QGraphicsItem .GraphicsItemFlag .ItemIsSelectable
            )
            self ._undo_stack .push (text_item )
            self ._drawing =False

        elif self ._tool ==Tool .STEP_MARKER :
            marker =StepMarkerItem (pos ,self ._color )
            self ._undo_stack .push (marker )
            self ._drawing =False

        elif self ._tool in (Tool .RECTANGLE ,Tool .ELLIPSE ,Tool .LINE ,
        Tool .ARROW ,Tool .BLUR ,Tool .HIGHLIGHT ,Tool .CROP ):
            pass

    def mouseMoveEvent (self ,event ):
        if not self ._drawing :
            return super ().mouseMoveEvent (event )

        pos =self .mapToScene (event .pos ())

        if self ._tool ==Tool .FREEHAND and self ._freehand_path :
            self ._freehand_path .lineTo (pos )
            self ._current_item .setPath (self ._freehand_path )
            return

        rect =QRectF (self ._start_pos ,pos ).normalized ()
        line =QLineF (self ._start_pos ,pos )

        if self ._current_item and self ._current_item .scene ():
            self ._scene .removeItem (self ._current_item )

        if self ._tool ==Tool .RECTANGLE :
            item =QGraphicsRectItem (rect )
            item .setPen (self ._pen ())
            item .setBrush (Qt .BrushStyle .NoBrush )
            self ._current_item =item
            self ._scene .addItem (item )

        elif self ._tool ==Tool .ELLIPSE :
            item =QGraphicsEllipseItem (rect )
            item .setPen (self ._pen ())
            item .setBrush (Qt .BrushStyle .NoBrush )
            self ._current_item =item
            self ._scene .addItem (item )

        elif self ._tool ==Tool .LINE :
            item =QGraphicsLineItem (line )
            item .setPen (self ._pen ())
            self ._current_item =item
            self ._scene .addItem (item )

        elif self ._tool ==Tool .ARROW :
            item =ArrowItem (line ,self ._pen ())
            self ._current_item =item
            self ._scene .addItem (item )

        elif self ._tool ==Tool .BLUR :
            item =BlurItem (rect ,self ._source_pixmap ,self ._blur_radius )
            self ._current_item =item
            self ._scene .addItem (item )

        elif self ._tool ==Tool .HIGHLIGHT :
            item =HighlightItem (rect ,self ._color ,self ._highlight_opacity )
            self ._current_item =item
            self ._scene .addItem (item )

        elif self ._tool ==Tool .CROP :
            if self ._crop_item and self ._crop_item .scene ():
                self ._scene .removeItem (self ._crop_item )
            self ._crop_item =QGraphicsRectItem (rect )
            self ._crop_item .setPen (QPen (QColor (0 ,120 ,215 ),2 ,Qt .PenStyle .DashLine ))
            self ._crop_item .setBrush (QBrush (QColor (0 ,120 ,215 ,30 )))
            self ._scene .addItem (self ._crop_item )
            self ._current_item =None

    def mouseReleaseEvent (self ,event ):
        if event .button ()!=Qt .MouseButton .LeftButton :
            return super ().mouseReleaseEvent (event )

        if not self ._drawing :
            return super ().mouseReleaseEvent (event )

        self ._drawing =False

        if self ._tool ==Tool .SELECT :
            super ().mouseReleaseEvent (event )
            return

        if self ._tool ==Tool .FREEHAND and self ._current_item :
            self ._scene .removeItem (self ._current_item )
            self ._undo_stack .push (self ._current_item )
            self ._current_item =None
            self ._freehand_path =None
            return

        if self ._tool ==Tool .CROP :
            pos =self .mapToScene (event .pos ())
            self ._crop_rect =QRectF (self ._start_pos ,pos ).normalized ()
            return

        if self ._current_item :
            if self ._current_item .scene ():
                self ._scene .removeItem (self ._current_item )
            self ._undo_stack .push (self ._current_item )
            self ._current_item =None

    def wheelEvent (self ,event ):
        if event .modifiers ()&Qt .KeyboardModifier .ControlModifier :
            factor =1.15 if event .angleDelta ().y ()>0 else 1 /1.15
            self .scale (factor ,factor )
        else :
            super ().wheelEvent (event )

    def undo (self ):
        self ._undo_stack .undo ()

    def redo (self ):
        self ._undo_stack .redo ()

    def apply_crop (self ):
        if not self ._crop_rect or self ._crop_rect .width ()<1 :
            return

        if self ._crop_item and self ._crop_item .scene ():
            self ._scene .removeItem (self ._crop_item )
            self ._crop_item =None

        full =self .render_to_pixmap ()
        cropped =full .copy (self ._crop_rect .toRect ())

        self ._reset_with_pixmap (cropped )
        self ._crop_rect =None

    def cancel_crop (self ):
        if self ._crop_item and self ._crop_item .scene ():
            self ._scene .removeItem (self ._crop_item )
            self ._crop_item =None
        self ._crop_rect =None

    def _reset_with_pixmap (self ,pixmap :QPixmap ):
        self ._scene .clear ()
        self ._source_pixmap =pixmap
        self ._scene .setSceneRect (QRectF (pixmap .rect ()))
        self ._bg_item =QGraphicsPixmapItem (pixmap )
        self ._bg_item .setZValue (-1000 )
        self ._scene .addItem (self ._bg_item )
        self ._undo_stack =UndoStack (self ._scene )
        StepMarkerItem .reset_counter ()
        self .fitInView (self ._bg_item ,Qt .AspectRatioMode .KeepAspectRatio )

    def render_to_pixmap (self )->QPixmap :
        rect =self ._scene .sceneRect ()
        pixmap =QPixmap (int (rect .width ()),int (rect .height ()))
        pixmap .fill (Qt .GlobalColor .white )
        painter =QPainter (pixmap )
        painter .setRenderHint (QPainter .RenderHint .Antialiasing )
        painter .setRenderHint (QPainter .RenderHint .SmoothPixmapTransform )
        self ._scene .render (painter ,QRectF (pixmap .rect ()),rect )
        painter .end ()
        return pixmap

    def reset_zoom (self ):
        self .resetTransform ()
        self .fitInView (self ._bg_item ,Qt .AspectRatioMode .KeepAspectRatio )

class AnnotationEditor (QMainWindow ):

    image_saved =pyqtSignal (str )

    def __init__ (self ,image_path :str ,config ,parent =None ):
        super ().__init__ (parent )
        self ._image_path =image_path
        self ._config =config
        self ._save_path =image_path

        pixmap =QPixmap (image_path )
        if pixmap .isNull ():
            raise ValueError (f"Cannot load image: {image_path }")

        self .setWindowTitle (f"BazzCap Editor — {os .path .basename (image_path )}")
        self .setMinimumSize (800 ,600 )

        self ._canvas =EditorCanvas (pixmap ,config ,self )
        self .setCentralWidget (self ._canvas )

        self ._build_toolbar ()
        self ._build_statusbar ()
        self ._setup_shortcuts ()

        self .showMaximized ()

    def _build_toolbar (self ):
        tb =QToolBar ("Tools",self )
        tb .setIconSize (QSize (24 ,24 ))
        tb .setMovable (False )
        self .addToolBar (Qt .ToolBarArea .TopToolBarArea ,tb )

        tools =[
        ("Select",Tool .SELECT ,"V"),
        ("Rectangle",Tool .RECTANGLE ,"R"),
        ("Ellipse",Tool .ELLIPSE ,"E"),
        ("Line",Tool .LINE ,"L"),
        ("Arrow",Tool .ARROW ,"A"),
        ("Freehand",Tool .FREEHAND ,"F"),
        ("Text",Tool .TEXT ,"T"),
        ("Blur",Tool .BLUR ,"B"),
        ("Highlight",Tool .HIGHLIGHT ,"H"),
        ("Steps",Tool .STEP_MARKER ,"N"),
        ("Crop",Tool .CROP ,"C"),
        ]

        self ._tool_actions ={}
        for name ,tool ,shortcut in tools :
            action =QAction (name ,self )
            action .setCheckable (True )
            action .setShortcut (shortcut )
            action .setToolTip (f"{name } ({shortcut })")
            action .triggered .connect (lambda checked ,t =tool :self ._set_tool (t ))
            tb .addAction (action )
            self ._tool_actions [tool ]=action

        self ._tool_actions [Tool .SELECT ].setChecked (True )

        tb .addSeparator ()

        self ._color_btn =QPushButton ()
        self ._color_btn .setFixedSize (28 ,28 )
        self ._update_color_button ()
        self ._color_btn .clicked .connect (self ._pick_color )
        self ._color_btn .setToolTip ("Pick color")
        tb .addWidget (QLabel ("  Color: "))
        tb .addWidget (self ._color_btn )

        tb .addWidget (QLabel ("  Width: "))
        self ._width_spin =QSpinBox ()
        self ._width_spin .setRange (1 ,30 )
        self ._width_spin .setValue (self ._canvas .line_width )
        self ._width_spin .valueChanged .connect (
        lambda v :setattr (self ._canvas ,'line_width',v )
        )
        tb .addWidget (self ._width_spin )

        tb .addWidget (QLabel ("  Font: "))
        self ._font_spin =QSpinBox ()
        self ._font_spin .setRange (8 ,72 )
        self ._font_spin .setValue (self ._canvas .font_size )
        self ._font_spin .valueChanged .connect (
        lambda v :setattr (self ._canvas ,'font_size',v )
        )
        tb .addWidget (self ._font_spin )

        tb .addSeparator ()

        undo_action =QAction ("Undo",self )
        undo_action .setShortcut ("Ctrl+Z")
        undo_action .triggered .connect (self ._canvas .undo )
        tb .addAction (undo_action )

        redo_action =QAction ("Redo",self )
        redo_action .setShortcut ("Ctrl+Y")
        redo_action .triggered .connect (self ._canvas .redo )
        tb .addAction (redo_action )

        tb .addSeparator ()

        self ._crop_apply =QAction ("Apply Crop",self )
        self ._crop_apply .triggered .connect (self ._apply_crop )
        self ._crop_apply .setVisible (False )
        tb .addAction (self ._crop_apply )

        self ._crop_cancel =QAction ("Cancel Crop",self )
        self ._crop_cancel .triggered .connect (self ._cancel_crop )
        self ._crop_cancel .setVisible (False )
        tb .addAction (self ._crop_cancel )

        tb .addSeparator ()

        zoom_reset =QAction ("Fit View",self )
        zoom_reset .setShortcut ("Ctrl+0")
        zoom_reset .triggered .connect (self ._canvas .reset_zoom )
        tb .addAction (zoom_reset )

        tb .addSeparator ()

        copy_action =QAction ("Copy",self )
        copy_action .setShortcut ("Ctrl+C")
        copy_action .triggered .connect (self ._copy_to_clipboard )
        tb .addAction (copy_action )

        save_action =QAction ("Save",self )
        save_action .setShortcut ("Ctrl+S")
        save_action .triggered .connect (self ._save )
        tb .addAction (save_action )

        save_as_action =QAction ("Save As",self )
        save_as_action .setShortcut ("Ctrl+Shift+S")
        save_as_action .triggered .connect (self ._save_as )
        tb .addAction (save_as_action )

        close_action =QAction ("Done",self )
        close_action .setShortcut ("Escape")
        close_action .triggered .connect (self .close )
        tb .addAction (close_action )

        self ._canvas .tool_changed .connect (self ._on_tool_changed )

    def _build_statusbar (self ):
        self ._status =QStatusBar (self )
        self .setStatusBar (self ._status )
        self ._status .showMessage ("Ready — select a tool and start drawing")

    def _setup_shortcuts (self ):
        pass

    def _set_tool (self ,tool :Tool ):
        self ._canvas .tool =tool
        for t ,action in self ._tool_actions .items ():
            action .setChecked (t ==tool )
        self ._status .showMessage (f"Tool: {tool .name }")

    def _on_tool_changed (self ,tool :Tool ):
        crop =(tool ==Tool .CROP )
        self ._crop_apply .setVisible (crop )
        self ._crop_cancel .setVisible (crop )

    def _pick_color (self ):
        color =QColorDialog .getColor (self ._canvas .color ,self ,"Pick Color")
        if color .isValid ():
            self ._canvas .color =color
            self ._update_color_button ()

    def _update_color_button (self ):
        c =self ._canvas .color
        self ._color_btn .setStyleSheet (
        f"background-color: {c .name ()}; border: 1px solid #666; border-radius: 4px;"
        )

    def _apply_crop (self ):
        self ._canvas .apply_crop ()
        self ._set_tool (Tool .SELECT )

    def _cancel_crop (self ):
        self ._canvas .cancel_crop ()
        self ._set_tool (Tool .SELECT )

    def _copy_to_clipboard (self ):
        pixmap =self ._canvas .render_to_pixmap ()
        import tempfile
        tmp =tempfile .NamedTemporaryFile (suffix =".png",delete =False )
        pixmap .save (tmp .name ,"PNG")
        tmp .close ()

        from bazzcap .clipboard import copy_image_to_clipboard
        if copy_image_to_clipboard (tmp .name ):
            self ._status .showMessage ("Copied to clipboard!")
        else :
            QApplication .clipboard ().setPixmap (pixmap )
            self ._status .showMessage ("Copied to clipboard (Qt)")

        try :
            os .unlink (tmp .name )
        except OSError :
            pass

    def _save (self ):
        pixmap =self ._canvas .render_to_pixmap ()
        if pixmap .save (self ._save_path ,None ,95 ):
            self ._status .showMessage (f"Saved: {self ._save_path }")
            self .image_saved .emit (self ._save_path )
        else :
            self ._status .showMessage ("Save failed!")

    def _save_as (self ):
        path ,_ =QFileDialog .getSaveFileName (
        self ,"Save Image",self ._save_path ,
        "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;All (*)",
        )
        if path :
            self ._save_path =path
            self ._save ()

    def closeEvent (self ,event ):
        self ._save ()
        event .accept ()
