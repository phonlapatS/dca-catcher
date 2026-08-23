import io
import logging
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use('Agg')  # Headless backend for server environment
import mplfinance as mpf

logger = logging.getLogger(__name__)

class ChartGenerator:
    """Generates stock charts with target price overlays using mplfinance."""

    @staticmethod
    def generate_target_chart(symbol: str, current_price: float, targets: list[float], period: str = "3mo") -> bytes | None:
        """
        Fetches stock data and generates a candlestick chart overlaid with 3 target lines.
        Returns the chart as raw PNG bytes.
        """
        try:
            # 1. Fetch 1 year of data upfront (single network call instead of up to 3)
            logger.info(f"Fetching chart data for {symbol}")
            ticker = yf.Ticker(symbol)
            df_full = ticker.history(period="1y")
            
            if df_full.empty:
                logger.warning(f"No chart data found for {symbol}")
                return None

            # Start with 3 months, expand only if targets extend below visible range
            df = df_full.tail(63)  # ~3 months of trading days
            
            if targets and min(targets) < df['Low'].min():
                df = df_full.tail(126)  # ~6 months
                if targets and min(targets) < df['Low'].min():
                    df = df_full  # Full year

            # Drop timezone information if any to avoid warnings in mplfinance
            if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # 2. Configure target lines (Blue palette for targets, Green for current price)
            target_line_color = '#0284c7'  # Blue
            target_badge_bg = '#bae6fd'    # Light Blue
            target_border_color = '#0369a1'

            all_target_prices = targets + [current_price]
            all_colors = [target_line_color for _ in targets] + ['#16a34a']
            
            hline_dict = dict(hlines=all_target_prices, colors=all_colors, linestyle='--', linewidths=1.5, alpha=0.85)

            # 3. Create BytesIO buffer
            buf = io.BytesIO()

            # 4. Generate Plot with natural mplfinance layout and custom text badges
            import matplotlib.pyplot as plt
            style = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle=':')
            title = f"{symbol} Target Zones"
            
            fig, axlist = mpf.plot(
                df,
                type='candle',
                style=style,
                hlines=hline_dict,
                title=title,
                ylabel='Price ($)',
                volume=False,
                tight_layout=True,
                returnfig=True
            )
            ax = axlist[0]

            # 5. Draw clear text badges on the lines (Black text on Light Blue badge)
            for idx, target in enumerate(targets):
                badge_text = f" T{idx+1}: ${target:,.2f} "
                ax.text(
                    0.015, target, badge_text,
                    transform=ax.get_yaxis_transform(),
                    color='#000000', fontsize=8.5, fontweight='bold',
                    va='center', ha='left',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor=target_badge_bg, edgecolor=target_border_color, linewidth=1.0, alpha=0.95)
                )

            # Current price badge (White text on Green badge)
            ax.text(
                0.015, current_price, f" Current: ${current_price:,.2f} ",
                transform=ax.get_yaxis_transform(),
                color='white', fontsize=8.5, fontweight='bold',
                va='center', ha='left',
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#16a34a', edgecolor='#15803d', linewidth=1.0, alpha=0.95)
            )

            # 6. Save and close
            fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
            plt.close(fig)
            
            buf.seek(0)
            return buf.read()
            
        except Exception as e:
            logger.error(f"Failed to generate chart for {symbol}: {e}")
            return None
