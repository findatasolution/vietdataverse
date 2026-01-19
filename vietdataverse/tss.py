import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_architecture():
    # Setup Figure (Dark Mode style for "Tech" feel)
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor('#0d1117') # GitHub Dark dim
    ax.set_facecolor('#0d1117')
    ax.axis('off')

    # Define Box Style
    def draw_box(x, y, width, height, color, label, sublabel=""):
        # Box
        rect = patches.FancyBboxPatch((x, y), width, height, 
                                      boxstyle="round,pad=0.1", 
                                      edgecolor='#30363d', 
                                      facecolor=color,
                                      linewidth=2, zorder=2)
        ax.add_patch(rect)
        # Main Label
        ax.text(x + width/2, y + height*0.65, label, 
                ha='center', va='center', fontsize=11, fontweight='bold', color='white', zorder=3)
        # Sub Label
        ax.text(x + width/2, y + height*0.35, sublabel, 
                ha='center', va='center', fontsize=8, color='#c9d1d9', zorder=3)
        return (x + width/2, y + height/2) # Return center

    # --- Draw Nodes ---
    
    # 1. Sources
    c_sources = draw_box(0.05, 0.6, 0.2, 0.15, '#238636', "Data Sources", "Websites & Yahoo API")
    
    # 2. Pipeline (GitHub Actions)
    c_actions = draw_box(0.35, 0.6, 0.2, 0.15, '#1f6feb', "Ingestion Engine", "GitHub Actions + Selenium")
    
    # 3. AI Agent
    c_ai = draw_box(0.35, 0.3, 0.2, 0.15, '#8e44ad', "AI Analysis", "Google Gemini 2.5")
    
    # 4. Database
    c_db = draw_box(0.65, 0.6, 0.2, 0.15, '#d29922', "Data Layer", "Neon PostgreSQL (Serverless)")
    
    # 5. Backend
    c_api = draw_box(0.65, 0.3, 0.2, 0.15, '#da3633', "Backend API", "FastAPI + Render")
    
    # 6. User/Frontend
    c_ui = draw_box(0.85, 0.45, 0.12, 0.15, '#3fb950', "Frontend", "GitHub Pages")

    # --- Draw Connections (Arrows) ---
    style = "Simple, tail_width=0.5, head_width=4, head_length=8"
    arrow_color = "#58a6ff"

    # Sources -> Actions
    ax.add_patch(patches.FancyArrowPatch((0.26, 0.675), (0.34, 0.675), connectionstyle="arc3,rad=0", arrowstyle=style, color=arrow_color))
    
    # Actions -> DB
    ax.add_patch(patches.FancyArrowPatch((0.56, 0.675), (0.64, 0.675), connectionstyle="arc3,rad=0", arrowstyle=style, color=arrow_color))
    
    # Actions -> AI (Trigger)
    ax.add_patch(patches.FancyArrowPatch((0.45, 0.59), (0.45, 0.46), connectionstyle="arc3,rad=0", arrowstyle=style, color=arrow_color))
    
    # AI -> DB (Save Analysis)
    ax.add_patch(patches.FancyArrowPatch((0.56, 0.375), (0.66, 0.59), connectionstyle="arc3,rad=-0.2", arrowstyle=style, color=arrow_color))
    
    # DB <-> API
    ax.add_patch(patches.FancyArrowPatch((0.75, 0.59), (0.75, 0.46), connectionstyle="arc3,rad=0", arrowstyle="<|-|>, head_width=4, head_length=8", color=arrow_color))
    
    # API <-> Frontend
    ax.add_patch(patches.FancyArrowPatch((0.83, 0.375), (0.87, 0.44), connectionstyle="arc3,rad=0.2", arrowstyle="<|-|>, head_width=4, head_length=8", color=arrow_color))

    # --- Title ---
    ax.text(0.5, 0.9, "VIET DATAVERSE ARCHITECTURE", ha='center', fontsize=18, fontweight='bold', color='white')
    ax.text(0.5, 0.85, "Automated • Serverless • AI-Powered", ha='center', fontsize=12, color='#8b949e')

    # Save
    plt.tight_layout()
    plt.savefig("viet_dataverse_architecture.png", dpi=300, bbox_inches='tight', facecolor='#0d1117')
    print("Chart saved as 'viet_dataverse_architecture.png'")

draw_architecture()