import yfinance as yf
import pandas as pd
import numpy as np
import time
import threading

class TopologicalEngine:
    def __init__(self):
        self.assets = {
            'GOLD': 'GC=F',  
            'OIL': 'CL=F',   
            'DXY': 'DX-Y.NYB',
            'SPX': '^GSPC',
            'BTC': 'BTC-USD',
            'VIX': '^VIX'
        }
        self.data_cache = {}
        self.correlation_matrix = None
        self.last_update = 0
        self.lock = threading.Lock()
        
        # Initialize with synthetic field so the graph is never blank on startup
        self._generate_synthetic_field()
        
    def fetch_global_liquidity(self):
        """Fetches recent price history for all tracked assets."""
        print("🕸️ Topological Engine: Fetching Global Liquidity Map...")
        
        chunk_data = {}
        # Fetch practically in parallel or batch if yfinance supported it well, 
        # but loop is fine for 6 assets.
        for name, ticker in self.assets.items():
            try:
                # Get last 5 days of 5m data if possible, else 1h
                # We need intraday for "live" feel, but 1d is better for stability.
                # Let's try 5d period, 15m interval for a balance of speed/detail.
                df = yf.download(ticker, period='5d', interval='15m', progress=False)
                if not df.empty:
                    chunk_data[name] = df['Close']
                else:
                    print(f"⚠️ Void detected: No liquidity found for {name} ({ticker})")
            except Exception as e:
                print(f"❌ Connection Severed to {name}: {e}")
                
        if len(chunk_data) > 1:
            # Align timestamps using concat
            try:
                self.data_cache = pd.concat(chunk_data, axis=1)
                self.data_cache.columns = chunk_data.keys()
                self.data_cache = self.data_cache.fillna(method='ffill').fillna(method='bfill')
                self.calculate_homology()
            except Exception as e:
                print(f"🕸️ Topology Data Alignment Error: {e}")
        else:
            print("⚠️ Topology: Insufficient Data, activating SIMULATION FIELD.")
            self._generate_synthetic_field()

    def _generate_synthetic_field(self):
        """Generates a synthetic correlation matrix for visualization when live data fails."""
        with self.lock:
            # Create a dummy correlation matrix
            assets = list(self.assets.keys())
            n = len(assets)
            # Random correlation matrix
            data = np.random.uniform(-1, 1, size=(n, n))
            # Make it symmetric and diagonal 1
            corr = (data + data.T) / 2
            np.fill_diagonal(corr, 1.0)
            
            self.correlation_matrix = pd.DataFrame(corr, columns=assets, index=assets)
            self.last_update = time.time()
            
    def calculate_homology(self):
        """Calculates the structure of the market (Correlations & Voids)."""
        if self.data_cache is None or self.data_cache.empty:
            return

        with self.lock:
            # 1. Rolling Correlation (Short term memory - last 20 bars)
            # This shows what's happening NOW, not historically.
            corr = self.data_cache.tail(50).corr()
            
            # Safety Check: If data is flat or NaN, corr will be bad.
            # Don't overwrite a good matrix with a bad one.
            if corr.dropna().empty or (corr.abs().sum().sum() == 0):
                # print("🕸️ Topology: Bad Correlation Matrix detected. Ignoring update.")
                return

            self.correlation_matrix = corr
            self.last_update = time.time()
            
            # Debug
            # print("\n🕸️ MARKET TOPOLOGY MATRIX (Last 50 periods):")
            # print(corr.round(2))

    def calculate_spectral_state(self):
        """
        Phase 34: The Eigenvalue Harvester.
        Calculates the 'Absorption Ratio' (Systemic Risk) using Matrix Spectral Analysis.
        
        Singularity: If 1st Eigenvalue explains > 85% of variance, the market is a Single Object.
        """
        if self.correlation_matrix is None: return None
        
        with self.lock:
            # Drop NaN
            c = self.correlation_matrix.fillna(0)
            if c.shape[0] < 2: return None
            
            # Eigen Decomposition
            try:
                # eigh for symmetric matrices
                eigenvalues, _ = np.linalg.eigh(c)
                
                # Sort descending
                eigenvalues = sorted(eigenvalues, reverse=True)
                
                # Absorption Ratio (Variance explained by 1st Mode)
                total_variance = sum(eigenvalues)
                absorption_ratio = eigenvalues[0] / total_variance if total_variance > 0 else 0
                
                # Dimensionality (How many modes matter?)
                # If AbsRatio is high, Dim is low (1).
                
                return {
                    'absorption_ratio': round(absorption_ratio, 4),
                    'is_singularity': absorption_ratio > 0.85,
                    'is_decoherence': absorption_ratio < 0.20,
                    'eigenvalues': [round(e, 2) for e in eigenvalues[:3]]
                }
            except Exception as e:
                print(f"🕸️ Spectral Analysis Failed: {e}")
                return None

    def check_godelian_fracture(self, spectral_data: dict, current_volatility: float) -> bool:
        """
        Phase 36: The Gödelian Arbitrageur.
        Detects 'Calm Fractures' -> Logic breaks before Price breaks.
        Condition: Low Volatility + High Decoherence.
        """
        if not spectral_data: return False
        
        is_calm = current_volatility < 0.005 # Very tight range (0.5%)
        is_decoherence = spectral_data.get('is_decoherence', False)
        
        # If the market is calm but the logic is fractured...
        if is_calm and is_decoherence:
            return True
            
        return False

    def get_topology_snapshot(self):
        """Returns nodes and links for the Force-Directed Graph."""
        # Use non-blocking lock to prevent API timeouts
        if not self.lock.acquire(timeout=2):
            # Lock is held by data fetch, return None to use cache
            return None
        try:
            if self.correlation_matrix is None:
                return None

            nodes = []
            links = []
            
                
            # Create Nodes
            for asset in self.correlation_matrix.columns:
                # Calculate 'Stress' (1 - Avg Correlation with others)
                avg_corr = self.correlation_matrix[asset].abs().mean()
                if pd.isna(avg_corr): avg_corr = 0.5 # Default to mid stress if NaN
                
                stress = 1.0 - avg_corr
                
                # Phase 31: The Silence Market (Vacuum Detection)
                # If an asset has ~0 correlation (0.00 to 0.05) with the market cluster
                # It is likely being "Held" or "Pinned" while the market moves.
                # This is a Vacuum.
                is_vacuum = False
                if 0.0 <= avg_corr < 0.08: # Very low correlation
                    is_vacuum = True
                
                nodes.append({
                    'id': asset,
                    'stress': round(float(stress), 2),
                    'group': 1 if asset in ['GOLD', 'OIL', 'BTC'] else 2,
                    'is_vacuum': is_vacuum
                })
                
            # Create Links (Springs)
            keys = self.correlation_matrix.columns
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    asset_a = keys[i]
                    asset_b = keys[j]
                    val = self.correlation_matrix.iloc[i, j]
                    
                    if pd.isna(val): val = 0.0
                    
                    # LOWERED THRESHOLD: Show more connections (0.05 instead of 0.1)
                    if abs(val) > 0.05: 
                        links.append({
                            'source': asset_a,
                            'target': asset_b,
                            'value': round(float(val), 2),
                            'type': 'positive' if val > 0 else 'negative'
                        })
            
            # Phase 32: Vacuum Resonance (Topological Mirrors)
            # A Vacuum is "Active" if its neighbors are under High Stress.
            # This implies the pinned asset is the "Eye of the Storm".
            
            # Map neighbor stress first
            neighbor_map = {}
            for link in links:
                s = link['source']
                t = link['target']
                if s not in neighbor_map: neighbor_map[s] = []
                if t not in neighbor_map: neighbor_map[t] = []
                neighbor_map[s].append(t)
                neighbor_map[t].append(s)
            
            # Update Nodes with Resonance
            for node in nodes:
                is_resonant = False
                if node.get('is_vacuum', False):
                    # Check neighbors
                    neighbors = neighbor_map.get(node['id'], [])
                    # Find stress of neighbors
                    for n_id in neighbors:
                        # Find neighbor node object
                        n_obj = next((x for x in nodes if x['id'] == n_id), None)
                        if n_obj and n_obj['stress'] > 0.7:
                            is_resonant = True
                            break
                
                node['is_resonant'] = is_resonant
            
            # Use FORCE SYNTHETIC if empty (Safety Net maintained)
            if len(links) == 0:
                print("🕸️ Topology: Weak/Empty Matrix detected. Engaging SYNTHETIC FIELD for visuals.")
                self.lock.release()  # Release before recursive call
                self._generate_synthetic_field()
                return self.get_topology_snapshot()

            print(f"🕸️ Topology Snapshot: {len(nodes)} Nodes, {len(links)} Links")
            
            # Phase 34: Spectral Analysis
            spectral = self.calculate_spectral_state()
            
            # Phase 36: Gödelian Fracture
            # We need current volatility to check for "Calm".
            # Approximating using Stress (High Stress usually = High Vol, so Low Stress = Low Vol?)
            # Better: Assume volatility is low if avg_stress is low.
            avg_stress = np.mean([n['stress'] for n in nodes]) if nodes else 0.5
            # Inverting stress for approximation: Low Stress ~ Low Volatility for now
            # Only a real volatility feed works best, but let's use the method locally logic
            is_godelian = self.check_godelian_fracture(spectral, avg_stress * 0.1) # Approx
            
            return {
                'timestamp': self.last_update,
                'nodes': nodes,
                'links': links,
                'spectral_analysis': spectral,
                'is_godelian_fracture': is_godelian
            }
        finally:
            # Always release the lock (unless already released for recursive call)
            if self.lock.locked():
                self.lock.release()

# Singleton instance
topology = TopologicalEngine()
