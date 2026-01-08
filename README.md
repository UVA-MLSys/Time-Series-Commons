# Time Series Commons

A modern, interactive platform for exploring time series datasets, research, and AI models. This website serves as a comprehensive resource hub for the time series research community.

## 🌟 Features

### Interactive Models Catalog
- **815+ Time Series Datasets**: Comprehensive collection from various domains including healthcare, finance, energy, environmental science, and more
- **Advanced Filtering**: Search by name, filter by domain, time interval, and benchmark participation
- **Benchmark Tracking**: Track which models have been evaluated across 80+ popular benchmarks including:
  - Foundation models (TimeGPT, Chronos, Tempo)
  - Classical models (Prophet, ARIMA, Informer)
  - Popular frameworks (AutoGluon, Darts, NeuralForecast)
- **Detailed Model Views**: Modal popups with complete dataset information, descriptions, and access links

### Research Showcase
- Project descriptions and publications
- Video presentations and talks
- Awards and achievements
- Contributor profiles

### Modern Design
- Clean, professional interface inspired by leading ML research sites
- Fully responsive design (mobile, tablet, desktop)
- Smooth animations and transitions
- Accessibility-focused with keyboard navigation

## 🚀 Quick Start

### Viewing the Website Locally

1. Clone or download this repository
2. Open `index.html` in a web browser
3. Navigate through the sections using the navigation bar

### Development Setup

No build process required! The website uses:
- Vanilla JavaScript (no frameworks)
- CSS3 with modern features
- JSON-based data management

## 📁 Project Structure

```
Time-Series-Commons/
├── index.html              # Main website
├── css/
│   └── styles.css         # All styling
├── js/
│   └── models.js          # Models catalog functionality
├── data/
│   └── models.json        # Dataset information (815+ models)
├── pics/
│   └── img/              # Images and logos
├── README.md             # This file
└── README-MODELS.md      # Guide for managing the models catalog
```

## 🔧 Managing the Models Catalog

The models catalog is powered by a single JSON file (`data/models.json`). This makes it easy to add, remove, or update dataset information without touching the code.

### Adding a New Dataset

1. Open `data/models.json`
2. Add a new entry following the schema:

```json
{
  "id": "my-dataset",
  "name": "My Dataset Name",
  "domain": "Domain Name",
  "variables": "Number of variables",
  "timePoints": "Number of time points",
  "interval": "Time interval",
  "repository": "Source repository",
  "dataLink": "Direct data link",
  "description": "Detailed description",
  "comments": "Additional notes",
  "benchmarks": {
    "Informer": true,
    "Prophet": true
  }
}
```

3. Save and refresh the website

For detailed instructions, see [README-MODELS.md](README-MODELS.md).

## 🎨 Design Philosophy

The website design is inspired by professional machine learning research sites, particularly the [Polymathic AI](https://polymathic-ai.org/) project, while maintaining a unique identity for Time Series Commons. Key design principles:

1. **Clean & Modern**: Minimal clutter, focus on content
2. **Professional**: Research-grade presentation
3. **Accessible**: Keyboard navigation, semantic HTML, ARIA labels
4. **Responsive**: Optimized for all screen sizes
5. **Fast**: Vanilla JavaScript, optimized assets

## 🔍 Key Technologies

- **HTML5**: Semantic markup
- **CSS3**: Grid, Flexbox, animations, responsive design
- **JavaScript (ES6+)**: Vanilla JS with modern features
- **JSON**: Data storage and management
- **Web Standards**: No frameworks or dependencies required

## 📊 Dataset Coverage

The models catalog includes datasets from:

- **Domains**: Healthcare, Finance, Energy, Transportation, Environmental Science, Sensor Data, Image Processing, Speech Recognition, and more
- **Scales**: From dozens to millions of time points
- **Intervals**: Hourly, Daily, Weekly, Monthly, Yearly, and custom intervals
- **Sources**: UCI, Kaggle, Academic repositories, Industry datasets
- **Benchmarks**: 80+ evaluation frameworks tracked

## 🤝 Contributing

### Adding Datasets
Follow the guide in [README-MODELS.md](README-MODELS.md) to add new datasets to the catalog.

### Reporting Issues
Found a bug or have a suggestion? Please open an issue with:
- Description of the problem or suggestion
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Browser and OS information

### Code Contributions
The codebase is intentionally simple and framework-free. When contributing:
- Follow existing code style
- Test in multiple browsers
- Ensure mobile responsiveness
- Update documentation as needed

## 🎓 Research Team

This project is maintained by the UVA Machine Learning Systems (MLSys) research group under the direction of Dr. Judy Fox.

### Mission
Advancing science and industry applications through time series analysis and developing AI systems that automatically recommend the best time series model for specific data and use cases.

## 📝 Citation

If you use datasets or information from this catalog in your research, please cite:

```bibtex
@misc{timeseriescommons2025,
  title={Time Series Commons: A Comprehensive Catalog of Time Series Datasets and Benchmarks},
  author={UVA Machine Learning Systems Research Group},
  year={2025},
  url={https://github.com/yourusername/Time-Series-Commons}
}
```

## 📄 License

The website code is available under the MIT License. Individual datasets may have their own licenses - please check the original source before use.

## 🔗 Related Projects

- [UVA-MLSys GitHub](https://github.com/UVA-MLSys)
- [Financial Time Series Forecasting with LLMs](https://uva-mlsys.github.io/Financial-Time-Series/)
- [COVID-19 Spatio-Temporal Analysis](https://uva-mlsys.github.io/gpce-covid/)
- [Time Series Sensitivity Analysis](https://uva-mlsys.github.io/SA-Timeseries/)

## 📧 Contact

For questions, collaborations, or feedback:
- Visit our research group website
- Check our publications and projects
- Connect with our team members

## 🙏 Acknowledgments

- Design inspiration from [Polymathic AI](https://polymathic-ai.org/)
- Dataset sources from the global time series research community
- NSF funding support for time series research
- All contributors and collaborators

---

**Built with ❤️ by the UVA Machine Learning Systems Research Group**

*Last Updated: January 2025*
