import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_architecture():
    # Setup Figure (Dark Mode style for "Tech" feel)
    # Using a dark background to make colors pop
    bg_color = '#0d1117' # GitHub Dark dim
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.axis('off')

    # Define Box Style Helper
    def draw_box(x, y, width, height, color, label, sublabel=""):
        # Create FancyBox with rounded corners
        rect = patches.FancyBboxPatch((x, y), width, height, 
                                      boxstyle="round,pad=0.02", 
                                      edgecolor='#30363d', 
                                      facecolor=color,
                                      linewidth=1.5, zorder=2)
        ax.add_patch(rect)
        
        # Add Main Label (Bold)
        ax.text(x + width/2, y + height*0.65, label, 
                ha='center', va='center', fontsize=11, fontweight='bold', 
                color='white', zorder=3)
        
        # Add Sub Label (Lighter text)
        ax.text(x + width/2, y + height*0.35, sublabel, 
                ha='center', va='center', fontsize=9, color='#e6edf3', zorder=3)
        
        return (x + width/2, y + height/2) # Return center coordinates

    # --- Draw Nodes ---
    
    # 1. Sources (Left)
    c_sources = draw_box(0.05, 0.6, 0.18, 0.15, '#238636', "Data Sources", "Websites & APIs")
    
    # 2. Ingestion Engine (Middle Left)
    c_actions = draw_box(0.30, 0.6, 0.22, 0.15, '#1f6feb', "Ingestion Engine", "GitHub Actions + Selenium")
    
    # 3. AI Agent (Below Ingestion)
    c_ai = draw_box(0.30, 0.3, 0.22, 0.15, '#8e44ad', "AI Analysis Agent", "Google Gemini 2.5")
    
    # 4. Data Layer (Middle Right)
    c_db = draw_box(0.60, 0.6, 0.20, 0.15, '#d29922', "Data Layer", "Neon PostgreSQL\n(Serverless)")
    
    # 5. Backend API (Below Data Layer)
    c_api = draw_box(0.60, 0.3, 0.20, 0.15, '#da3633', "Backend API", "FastAPI + Render")
    
    # 6. Frontend (Far Right)
    c_ui = draw_box(0.88, 0.45, 0.10, 0.15, '#3fb950', "Frontend", "GitHub Pages")

    # --- Draw Connections (Arrows) ---
    style = "Simple, tail_width=0.5, head_width=5, head_length=5"
    arrow_color = "#58a6ff"

    # Arrow: Sources -> Actions
    ax.add_patch(patches.FancyArrowPatch((0.23, 0.675), (0.30, 0.675), 
                                         connectionstyle="arc3,rad=0", 
                                         arrowstyle=style, color=arrow_color))
    
    # Arrow: Actions -> DB
    ax.add_patch(patches.FancyArrowPatch((0.52, 0.675), (0.60, 0.675), 
                                         connectionstyle="arc3,rad=0", 
                                         arrowstyle=style, color=arrow_color))
    
    # Arrow: Actions -> AI (Trigger)
    ax.add_patch(patches.FancyArrowPatch((0.41, 0.60), (0.41, 0.45), 
                                         connectionstyle="arc3,rad=0", 
                                         arrowstyle=style, color=arrow_color))
    
    # Arrow: AI -> DB (Save Analysis) - Curved arrow
    ax.add_patch(patches.FancyArrowPatch((0.52, 0.375), (0.60, 0.62), 
                                         connectionstyle="arc3,rad=-0.1", 
                                         arrowstyle=style, color=arrow_color))
    
    # Arrow: DB <-> API (Bi-directional)
    ax.add_patch(patches.FancyArrowPatch((0.70, 0.60), (0.70, 0.45), 
                                         connectionstyle="arc3,rad=0", 
                                         arrowstyle="<|-|>, head_width=5, head_length=5", 
                                         color=arrow_color))
    
    # Arrow: API <-> Frontend (Bi-directional)
    ax.add_patch(patches.FancyArrowPatch((0.80, 0.375), (0.88, 0.48), 
                                         connectionstyle="arc3,rad=0.1", 
                                         arrowstyle="<|-|>, head_width=5, head_length=5", 
                                         color=arrow_color))

    # --- Title ---
    ax.text(0.5, 0.92, "VIET DATAVERSE ARCHITECTURE", 
            ha='center', fontsize=20, fontweight='bold', color='white')
    ax.text(0.5, 0.87, "Automated • Serverless • AI-Powered", 
            ha='center', fontsize=12, color='#8b949e')

    # Save
    plt.tight_layout()
    plt.savefig("viet_dataverse_architecture.png", dpi=150, facecolor=bg_color)
    plt.show()

draw_architecture()