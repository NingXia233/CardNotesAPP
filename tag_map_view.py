import sys
import json
import math
from PyQt6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsTextItem, QGraphicsItem, QGraphicsLineItem, QInputDialog
)
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QBrush, QPen, QFont, QPainter, QCloseEvent

class TagConnection(QGraphicsLineItem):
    """Represents a labeled connection between two TagNodes."""
    def __init__(self, start_node, end_node, label=""):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.label = label

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        pen = QPen(Qt.GlobalColor.darkGray)
        pen.setWidth(2)
        self.setPen(pen)

        self.start_node.add_edge(self)
        self.end_node.add_edge(self)

        self.text_item = QGraphicsTextItem(self.label, self)
        font = QFont()
        font.setPointSize(9)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(Qt.GlobalColor.darkBlue)
        
        self.update_position()

    def get_data(self):
        """Returns data for serialization."""
        return {
            "start": self.start_node.tag_name,
            "end": self.end_node.tag_name,
            "label": self.label
        }

    def update_position(self):
        """Updates the line's start/end points and the label's position."""
        # Create lines from each node's center to the other's center, but in the node's local coordinates
        line_for_start_node = QLineF(QPointF(0, 0), self.start_node.mapFromScene(self.end_node.pos()))
        line_for_end_node = QLineF(QPointF(0, 0), self.end_node.mapFromScene(self.start_node.pos()))

        # Calculate intersection points in local coordinates
        start_intersect_local = self.start_node.get_intersection_point(line_for_start_node)
        end_intersect_local = self.end_node.get_intersection_point(line_for_end_node)

        # Map local intersection points back to scene coordinates
        start_pos = self.start_node.mapToScene(start_intersect_local)
        end_pos = self.end_node.mapToScene(end_intersect_local)

        # Set the line
        self.setLine(QLineF(start_pos, end_pos))

        # Update label position to be in the middle of the new line
        center_x = (start_pos.x() + end_pos.x()) / 2
        center_y = (start_pos.y() + end_pos.y()) / 2
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(center_x - text_rect.width() / 2, center_y - text_rect.height() / 2)

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            pen = self.pen()
            pen.setColor(Qt.GlobalColor.red)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(self.line())
        else:
            super().paint(painter, option, widget)

class TagNode(QGraphicsItem):
    """A draggable node representing a tag."""
    def __init__(self, tag_name):
        super().__init__()
        self.tag_name = tag_name
        self.edges = []

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

        self.ellipse = QGraphicsEllipseItem(-45, -15, 90, 30, self)
        self.ellipse.setBrush(QBrush(Qt.GlobalColor.lightGray))
        self.pen = QPen(Qt.GlobalColor.black)
        self.ellipse.setPen(self.pen)

        self.text = QGraphicsTextItem(self.tag_name, self)
        font = QFont()
        font.setPointSize(10)
        self.text.setFont(font)
        text_rect = self.text.boundingRect()
        self.text.setPos(-text_rect.width() / 2, -text_rect.height() / 2)

    def get_intersection_point(self, line: QLineF) -> QPointF:
        """
        Calculates the intersection point of the line with the node's ellipse.
        The line should be in the node's coordinate system, starting from the center (0,0).
        """
        ellipse_rect = self.ellipse.rect()
        rx = ellipse_rect.width() / 2
        ry = ellipse_rect.height() / 2
        p2 = line.p2()

        if p2.x() == 0 and p2.y() == 0: # Should not happen if nodes are distinct
             return QPointF(0,0)

        if abs(p2.x()) < 1e-6: # Line is vertical or near-vertical
            return QPointF(0, ry if p2.y() > 0 else -ry)
        
        m = p2.y() / p2.x()
        
        # Ellipse equation: (x/rx)^2 + (y/ry)^2 = 1
        # Line equation: y = mx
        # Substitute y in ellipse equation: x^2/rx^2 + (mx)^2/ry^2 = 1
        # x^2 * (1/rx^2 + m^2/ry^2) = 1
        # x^2 = 1 / (1/rx^2 + m^2/ry^2)
        
        x_squared = 1 / (1/(rx*rx) + (m*m)/(ry*ry))
        x = math.sqrt(x_squared)
        
        if p2.x() < 0:
            x = -x
            
        y = m * x
        return QPointF(x, y)

    def get_data(self):
        """Returns data for serialization."""
        pos = self.pos()
        return {"x": pos.x(), "y": pos.y()}

    def add_edge(self, edge):
        self.edges.append(edge)

    def remove_edge(self, edge):
        if edge in self.edges:
            self.edges.remove(edge)

    def set_highlighted(self, highlighted):
        """Set the visual highlight state for connection."""
        if highlighted:
            self.pen.setColor(Qt.GlobalColor.cyan)
            self.pen.setWidth(3)
        else:
            self.pen.setColor(Qt.GlobalColor.black)
            self.pen.setWidth(1)
        self.ellipse.setPen(self.pen)

    def boundingRect(self):
        return self.ellipse.boundingRect()

    def paint(self, painter, option, widget):
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_position()
        return super().itemChange(change, value)

class TagMapScene(QGraphicsScene):
    """The scene for the tag map, handling interactions."""
    def __init__(self, tags, layout_data, parent=None):
        super().__init__(parent)
        self.nodes = {}
        self.start_node = None
        self.update_scene(tags, layout_data)

    def _find_next_available_pos(self, occupied_positions, center_x=0.0, center_y=0.0):
        """Finds the next available position in a spiral pattern."""
        r = 150  # Initial radius
        theta = 0
        step = 30  # Angle step in degrees
        radius_increment = 10

        while True:
            angle_rad = math.radians(theta)
            x = center_x + r * math.cos(angle_rad)
            y = center_y + r * math.sin(angle_rad)
            
            # Check for collision with existing nodes
            is_occupied = False
            for pos in occupied_positions:
                # Using a simple distance check. Node width is ~90, height is ~30.
                # A safe distance would be around 120 horizontally and 50 vertically.
                if abs(pos[0] - x) < 120 and abs(pos[1] - y) < 50:
                    is_occupied = True
                    break
            
            if not is_occupied:
                return x, y

            theta += step
            if theta >= 360:
                theta = 0
                r += radius_increment

    def update_scene(self, tags, layout_data):
        """Update the scene with a new set of tags and layout data."""
        self.tags = tags
        self.layout_data = layout_data if layout_data else {}
        
        # Remove nodes for tags that no longer exist
        current_node_tags = list(self.nodes.keys())
        for tag_name in current_node_tags:
            if tag_name not in self.tags:
                node_to_remove = self.nodes.pop(tag_name)
                self.removeItem(node_to_remove)

        # Remove all connections, they will be recreated
        for item in self.items():
            if isinstance(item, TagConnection):
                self.removeItem(item)

        self.populate_scene()

    def populate_scene(self):
        """Populate the scene with nodes and connections from data."""
        node_positions_from_file = self.layout_data.get("nodes", {})
        occupied_positions = set()
        placed_tags = set()

        # First pass: position nodes that have a saved position
        for tag_name in self.tags:
            if tag_name not in self.nodes:
                node = TagNode(tag_name)
                self.addItem(node)
                self.nodes[tag_name] = node
            
            node = self.nodes[tag_name]
            pos_data = node_positions_from_file.get(tag_name)
            
            if pos_data and 'x' in pos_data and 'y' in pos_data:
                pos_tuple = (pos_data['x'], pos_data['y'])
                node.setPos(pos_tuple[0], pos_tuple[1])
                occupied_positions.add(pos_tuple)
                placed_tags.add(tag_name)

        # Second pass: layout new nodes that were not in the layout file
        new_tags = set(self.tags) - placed_tags
        
        # Find a center point for the spiral layout
        center_x, center_y = 0.0, 0.0
        if occupied_positions:
            sum_x = sum(p[0] for p in occupied_positions)
            sum_y = sum(p[1] for p in occupied_positions)
            # Check length to avoid division by zero
            if len(occupied_positions) > 0:
                center_x = sum_x / len(occupied_positions)
                center_y = sum_y / len(occupied_positions)

        for tag_name in sorted(list(new_tags)): # Sort for deterministic layout
            node = self.nodes[tag_name]
            new_x, new_y = self._find_next_available_pos(occupied_positions, center_x, center_y)
            node.setPos(new_x, new_y)
            occupied_positions.add((new_x, new_y))
        
        # Re-create connections based on the current nodes
        connections = self.layout_data.get("connections", [])
        for conn_data in connections:
            start_node = self.nodes.get(conn_data["start"])
            end_node = self.nodes.get(conn_data["end"])
            if start_node and end_node:
                # Avoid creating duplicate connections
                already_exists = False
                for edge in start_node.edges:
                    if edge.end_node == end_node:
                        already_exists = True
                        break
                if not already_exists:
                    connection = TagConnection(start_node, end_node, conn_data.get("label", ""))
                    self.addItem(connection)

    def get_layout_data(self):
        """Export the current scene layout to a dictionary."""
        nodes_data = {}
        connections_data = []
        for item in self.items():
            if isinstance(item, TagNode):
                nodes_data[item.tag_name] = item.get_data()
            elif isinstance(item, TagConnection):
                connections_data.append(item.get_data())
        return {"nodes": nodes_data, "connections": connections_data}

    def mousePressEvent(self, event):
        """Handle node clicks to create connections, allowing movement."""
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        
        node = None
        if isinstance(item, TagNode):
            node = item
        elif item and isinstance(item.parentItem(), TagNode):
            node = item.parentItem()

        if node:
            # This is a click on a node, not a drag.
            # The drag is handled by the item's own event handling.
            # We only implement the connection logic here.
            if not self.start_node:
                self.start_node = node
                self.start_node.set_highlighted(True)
            elif self.start_node != node:
                label, ok = QInputDialog.getText(self.views()[0], "Connection Label", "Enter label for the connection:")
                if ok:
                    connection = TagConnection(self.start_node, node, label)
                    self.addItem(connection)
                self.start_node.set_highlighted(False)
                self.start_node = None
            else:
                self.start_node.set_highlighted(False)
                self.start_node = None
            # We don't call super, to prevent the scene from starting a drag
            # which would interfere with the item's own drag implementation.
        else:
            if self.start_node:
                self.start_node.set_highlighted(False)
                self.start_node = None
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Handle the Delete key to remove selected connections."""
        if event.key() == Qt.Key.Key_Delete:
            for item in self.selectedItems():
                if isinstance(item, TagConnection):
                    item.start_node.remove_edge(item)
                    item.end_node.remove_edge(item)
                    self.removeItem(item)
        else:
            super().keyPressEvent(event)

class TagMapWindow(QGraphicsView):
    """The window for displaying the tag map."""
    def __init__(self, tags, layout_data, save_callback):
        super().__init__()
        self.setWindowTitle('Tag Map')
        self.setMinimumSize(800, 600)
        self.save_callback = save_callback

        self.scene = TagMapScene([], {}, self) # Start with an empty scene
        self.setScene(self.scene)
        self.update_tags(tags, layout_data)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def update_tags(self, tags, layout_data=None):
        """Update the tags displayed in the map."""
        if layout_data is None:
            layout_data = self.scene.get_layout_data()
        self.scene.update_scene(tags, layout_data)

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event to trigger saving."""
        layout_data = self.scene.get_layout_data()
        self.save_callback(layout_data)
        super().closeEvent(event)
