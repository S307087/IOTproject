import cherrypy
import sqlite3
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILENAME = os.path.join(BASE_DIR, 'catalog.db')

def get_db():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn

class CatalogAPI(object):
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {"status": "ok", "service": "Market Catalog API"}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register_shelf(self):
        """ Register a Smart Shelf and return its authorized configuration. """
        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(405)
        
        data = cherrypy.request.json
        shelf_id = data.get("shelf_id")
        
        conn = get_db()
        shelf = conn.execute("SELECT * FROM shelves WHERE shelf_id = ?", (shelf_id,)).fetchone()
        conn.close()
        
        if shelf:
            return {
                "shelf_id": shelf["shelf_id"],
                "product_ids": json.loads(shelf["product_ids"]) if shelf["product_ids"] else [],
                "max_capacity": shelf["max_capacity"] or 0,
                "proportions": json.loads(shelf["proportions"]) if shelf["proportions"] else {}
            }
        raise cherrypy.HTTPError(404, "Shelf not found")

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_inventory(self):
        """ Called by Alert System to actually update catalog.db when an RFID is confirmed added/removed """
        if cherrypy.request.method != 'PUT':
            raise cherrypy.HTTPError(405)
            
        data = cherrypy.request.json
        rfid = data.get("rfid")
        action = data.get("action") # "added" or "removed"
        shelf_id = data.get("shelf_id")
        
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Identity product
        tag = cursor.execute("SELECT product_id FROM rfid_tags WHERE rfid_id = ?", (rfid,)).fetchone()
        if not tag:
            conn.close()
            raise cherrypy.HTTPError(404, f"RFID {rfid} not found in database")
            
        product_id = tag["product_id"]
        
        if action == "removed":
            # Remove from shelf_stock
            cursor.execute("UPDATE products SET shelf_stock = max(0, shelf_stock - 1) WHERE product_id = ?", (product_id,))
        elif action == "added":
            cursor.execute("UPDATE products SET shelf_stock = shelf_stock + 1 WHERE product_id = ?", (product_id,))
            
        conn.commit()
        # return new state   
        prod_row = cursor.execute("SELECT shelf_stock, warehouse_stock FROM products WHERE product_id = ?", (product_id,)).fetchone()
        
        conn.commit()
        print(f"[CatalogAPI] Successfully updated inventory! Product {product_id} shelf stock is now: {prod_row['shelf_stock']} / Warehouse: {prod_row['warehouse_stock']}")
        conn.close()
        
        return {
            "status": "success",
            "product_id": product_id,
            "shelf_stock": prod_row["shelf_stock"] if prod_row else 0,
            "warehouse_stock": prod_row["warehouse_stock"] if prod_row else 0
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_product_by_rfid(self, rfid=None):
        if not rfid:
            raise cherrypy.HTTPError(400, "Missing rfid parameter")
            
        conn = get_db()
        tag = conn.execute("SELECT product_id FROM rfid_tags WHERE rfid_id = ?", (rfid,)).fetchone()
        if not tag:
            conn.close()
            raise cherrypy.HTTPError(404, "RFID not found")
            
        product_id = tag["product_id"]
        prod = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
        conn.close()
        
        if prod:
            return dict(prod)
        raise cherrypy.HTTPError(404, "Product not found")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_product(self, product_id=None):
        if not product_id:
            raise cherrypy.HTTPError(400, "Missing product_id")
        conn = get_db()
        prod = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
        shelf_info = conn.execute("SELECT max_capacity, proportions, product_ids FROM shelves WHERE shelf_id = ?", (prod["shelf_id"],)).fetchone() if prod and prod["shelf_id"] else None
        conn.close()
        if prod:
            res = dict(prod)
            if shelf_info:
                res["shelf_max_capacity"] = shelf_info["max_capacity"]
                res["shelf_proportions"] = json.loads(shelf_info["proportions"] if shelf_info["proportions"] else "{}")
                res["shelf_product_ids"] = json.loads(shelf_info["product_ids"] if shelf_info["product_ids"] else "[]")
            return res
        raise cherrypy.HTTPError(404, "Product not found")

if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080,
        'log.screen': True
    })
    
    # Enable CORS for potential future frontends
    def cors():
        cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
        cherrypy.response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        cherrypy.response.headers["Access-Control-Allow-Headers"] = "Content-Type"

    cherrypy.tools.cors = cherrypy.Tool('before_handler', cors)
    
    conf = {
        '/': {
            'tools.cors.on': True
        }
    }
    
    print("Starting Market Catalog REST API on port 8080...")
    cherrypy.quickstart(CatalogAPI(), '/', conf)
