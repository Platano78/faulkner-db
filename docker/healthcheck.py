#!/usr/bin/env python3
import http.server
import socketserver
import os

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            # Check dependencies
            try:
                # Check FalkorDB connection
                import redis
                r = redis.Redis(host=os.getenv('FALKORDB_HOST', 'falkordb'), 
                               port=int(os.getenv('FALKORDB_PORT', 6379)))
                r.ping()
                
                # Check PostgreSQL connection
                import psycopg2
                conn = psycopg2.connect(
                    host=os.getenv('POSTGRES_HOST', 'postgres'),
                    port=int(os.getenv('POSTGRES_PORT', 5432)),
                    database=os.getenv('POSTGRES_DB', 'graphiti'),
                    user=os.getenv('POSTGRES_USER', 'graphiti'),
                    password=os.getenv('POSTGRES_PASSWORD', 'graphiti123')
                )
                conn.close()
                
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Healthy')
            except Exception as e:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(f'Unhealthy: {str(e)}'.encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    with socketserver.TCPServer(('', port), HealthCheckHandler) as httpd:
        print(f'Health check server running on port {port}')
        httpd.serve_forever()
