# SkillCorner X PySport Analytics Cup
This repository contains my submission for the SkillCorner X PySport Analytics Cup **Analyst Track**. 

Find the Analytics Cup [**dataset**](https://github.com/SkillCorner/opendata/tree/master/data) and [**tutorials**](https://github.com/SkillCorner/opendata/tree/master/resources) on the [**SkillCorner Open Data Repository**](https://github.com/SkillCorner/opendata).

## Analyst Track Submission

## Introduction

The application is built on top of the PySport ecosystem using skillcorner data and focuses on modular components and reusable widgets, allowing analysts to quickly access key insights without complex setup.

---

## Use Case(s)

We address several key use cases including:

* **Individual player performance analysis** through dedicated player focus pages with customizable widgets
* **Team comparison** for tactical analysis
* **Match analysis** for opposition scouting and preparation
* **Personal dashboard creation**, allowing analysts to build their own analytical workspace

At this stage, the **Player Focus module** is almost fully implemented. It demonstrates the platform’s ability to deliver in-depth player-level insights, including:

* Playstyle detection of the player
* Ranking of the player based on percentiles indicators
* Heatmap of the player

---

## Potential Audience

Primary users include:

* Football analysts at professional clubs
* Data scientists working in sports organizations
* Scouts evaluating player performance
* Academic researchers in football analytics
* Passionated fans !

Thanks to its modular design and intuitive interface, the platform is also well suited for **coaching staff** seeking data-driven insights for tactical planning and player development.

---

## Video URL

https://youtu.be/LECzE20SO-s

---

## Run Instructions

### Prerequisites

* Conda (Miniconda or Anaconda)
* Python **3.12**
* Git

---

### Installation Steps

#### 1. Clone the repository

```bash
git clone [your-repository-url]
cd pysport-analytics
```

#### 2. Create and activate the Conda environment

```bash
conda create --yes --name analyst_cup python=3.12
conda activate analyst_cup
```

#### 3. Install dependencies

```bash
pip install -r requirements.txt
```

#### 4. Run the application

```bash
python main.py
```

---

### Access the application

Open your web browser and navigate to:

```text
http://127.0.0.1:8050/
```

---

### Notes

* Data is automatically loaded from the **SkillCorner GitHub repository**
* The first launch may take a short time due to data fetching and caching
* No local data files are required or included in the repository

---

## Current Status & Known Issues

### ✅ Implemented

* Player Focus Page with multiple interactive widgets
* Data loading from SkillCorner’s GitHub repository
* Modular widget system with reusable components
* Responsive design across different screen sizes

### 🚧 In Development (Future Updates)

* Fully customizable dashboards with drag-and-drop widgets
* Additional pages: team comparison, match analysis, player comparison
* Widget UI/UX refinements, especially in focus modes
* Architecture refactoring toward a unified plug-and-play system
* Global search for players, matches, and teams
* Layout persistence (save and reload custom dashboards)
* Improved support for substitutes and goalkeepers

### ⚠️ Known Bugs

* Default player selection in filters requires adjustment
* Minor styling issues in widget focus modes
* Limited support for goalkeepers and substitute players

---

## Technical Stack

* **Framework**: Dash (Plotly) for interactive web applications
* **Backend**: Python 3.12 with pandas and numpy for data processing
* **Frontend**: HTML, CSS, JavaScript with Plotly.js for visualizations
* **Deployment**: Local server with cloud deployment potential
* **Data Source**: SkillCorner Open Data Repository (GitHub)

---

## License

**MIT License** — see the `LICENSE` file for details.

---

## [Optional] Web App / Website URL

Comming soon