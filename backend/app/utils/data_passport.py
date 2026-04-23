"""
Data Passport Generator - Schema-First Architecture
Extracts metadata from large DataFrames without sending raw data to LLM.
Handles 100k+ rows x 1000+ columns efficiently.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import hashlib
from datetime import datetime


class DataPassport:
    """
    Generates a compact metadata representation of a DataFrame.
    This "passport" contains everything the LLM needs to write code
    WITHOUT seeing the actual data rows.
    """
    
    def __init__(self, df: pd.DataFrame, max_sample_rows: int = 5):
        """
        Args:
            df: The DataFrame to analyze
            max_sample_rows: Number of sample rows to include (default: 5)
        """
        self.df = df
        self.max_sample_rows = max_sample_rows
        self.passport = self._generate_passport()
    
    def _generate_passport(self) -> Dict[str, Any]:
        """Generate the complete data passport."""
        return {
            "metadata": self._get_metadata(),
            "schema": self._get_schema(),
            "statistics": self._get_statistics(),
            "sample_data": self._get_sample_data(),
            "data_quality": self._get_data_quality(),
            "relationships": self._detect_relationships(),
            "fingerprint": self._get_fingerprint()
        }
    
    def _get_metadata(self) -> Dict[str, Any]:
        """Extract basic metadata about the DataFrame."""
        return {
            "shape": {
                "rows": len(self.df),
                "columns": len(self.df.columns)
            },
            "memory_usage_mb": self.df.memory_usage(deep=True).sum() / 1024**2,
            "timestamp": datetime.now().isoformat(),
            "total_cells": len(self.df) * len(self.df.columns)
        }
    
    def _get_schema(self) -> List[Dict[str, Any]]:
        """
        Extract detailed schema information for each column.
        This is the CORE of the passport - column definitions.
        """
        schema = []
        
        for col in self.df.columns:
            col_data = self.df[col]
            
            col_info = {
                "name": col,
                "dtype": str(col_data.dtype),
                "python_type": self._infer_python_type(col_data),
                "nullable": col_data.isnull().any(),
                "unique_count": int(col_data.nunique()),
                "null_count": int(col_data.isnull().sum()),
                "null_percentage": float(col_data.isnull().sum() / len(col_data) * 100)
            }
            
            # Add type-specific information
            if pd.api.types.is_numeric_dtype(col_data):
                col_info["category"] = "numeric"
                col_info["statistics"] = self._get_numeric_stats(col_data)
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                col_info["category"] = "datetime"
                col_info["statistics"] = self._get_datetime_stats(col_data)
            elif pd.api.types.is_categorical_dtype(col_data) or pd.api.types.is_object_dtype(col_data):
                col_info["category"] = "categorical"
                col_info["statistics"] = self._get_categorical_stats(col_data)
            else:
                col_info["category"] = "other"
            
            schema.append(col_info)
        
        return schema
    
    def _get_numeric_stats(self, series: pd.Series) -> Dict[str, Any]:
        """Get statistics for numeric columns."""
        clean_series = series.dropna()
        
        if len(clean_series) == 0:
            return {"error": "All values are null"}
        
        return {
            "min": float(clean_series.min()),
            "max": float(clean_series.max()),
            "mean": float(clean_series.mean()),
            "median": float(clean_series.median()),
            "std": float(clean_series.std()) if len(clean_series) > 1 else 0.0,
            "q25": float(clean_series.quantile(0.25)),
            "q75": float(clean_series.quantile(0.75)),
            "skewness": float(clean_series.skew()),
            "kurtosis": float(clean_series.kurtosis()),
            "zeros_count": int((clean_series == 0).sum()),
            "positive_count": int((clean_series > 0).sum()),
            "negative_count": int((clean_series < 0).sum())
        }
    
    def _get_datetime_stats(self, series: pd.Series) -> Dict[str, Any]:
        """Get statistics for datetime columns."""
        clean_series = series.dropna()
        
        if len(clean_series) == 0:
            return {"error": "All values are null"}
        
        return {
            "min": str(clean_series.min()),
            "max": str(clean_series.max()),
            "range_days": (clean_series.max() - clean_series.min()).days if len(clean_series) > 0 else 0,
            "unique_dates": int(clean_series.nunique())
        }
    
    def _get_categorical_stats(self, series: pd.Series) -> Dict[str, Any]:
        """Get statistics for categorical/text columns."""
        clean_series = series.dropna()
        
        if len(clean_series) == 0:
            return {"error": "All values are null"}
        
        value_counts = clean_series.value_counts()
        
        # Sample values - not all of them (avoid token bloat)
        top_values = value_counts.head(10).to_dict()
        
        stats = {
            "unique_values": int(clean_series.nunique()),
            "most_common": str(value_counts.index[0]) if len(value_counts) > 0 else None,
            "most_common_count": int(value_counts.iloc[0]) if len(value_counts) > 0 else 0,
            "top_10_values": {str(k): int(v) for k, v in top_values.items()}
        }
        
        # If text, get length statistics
        if pd.api.types.is_object_dtype(series):
            lengths = clean_series.astype(str).str.len()
            stats["text_length"] = {
                "min": int(lengths.min()),
                "max": int(lengths.max()),
                "mean": float(lengths.mean())
            }
        
        return stats
    
    def _get_statistics(self) -> Dict[str, Any]:
        """Get overall dataset statistics."""
        return {
            "total_null_cells": int(self.df.isnull().sum().sum()),
            "null_percentage": float(self.df.isnull().sum().sum() / (len(self.df) * len(self.df.columns)) * 100),
            "duplicate_rows": int(self.df.duplicated().sum()),
            "numeric_columns": int(self.df.select_dtypes(include=[np.number]).shape[1]),
            "categorical_columns": int(self.df.select_dtypes(include=['object', 'category']).shape[1]),
            "datetime_columns": int(self.df.select_dtypes(include=['datetime64']).shape[1])
        }
    
    def _get_sample_data(self) -> Dict[str, Any]:
        """
        Get a small sample of the data for context.
        LIMITED to max_sample_rows to avoid token overflow.
        """
        sample_df = self.df.head(self.max_sample_rows)
        
        return {
            "rows": sample_df.to_dict(orient='records'),
            "count": len(sample_df),
            "note": f"Showing first {self.max_sample_rows} rows only. Full dataset has {len(self.df)} rows."
        }
    
    def _get_data_quality(self) -> Dict[str, Any]:
        """Assess data quality metrics."""
        quality_issues = []
        
        # Check for high null percentage columns
        for col in self.df.columns:
            null_pct = self.df[col].isnull().sum() / len(self.df) * 100
            if null_pct > 50:
                quality_issues.append({
                    "column": col,
                    "issue": "high_null_percentage",
                    "value": float(null_pct)
                })
        
        # Check for constant columns
        for col in self.df.columns:
            if self.df[col].nunique() == 1:
                quality_issues.append({
                    "column": col,
                    "issue": "constant_value",
                    "value": str(self.df[col].iloc[0])
                })
        
        return {
            "issues_count": len(quality_issues),
            "issues": quality_issues[:10],  # Limit to top 10 issues
            "completeness_score": float(100 - (self.df.isnull().sum().sum() / (len(self.df) * len(self.df.columns)) * 100))
        }
    
    def _detect_relationships(self) -> List[Dict[str, Any]]:
        """
        Detect potential relationships between columns.
        Useful for suggesting joins or correlations.
        """
        relationships = []
        
        # Correlation for numeric columns
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            corr_matrix = self.df[numeric_cols].corr()
            
            # Find strong correlations (> 0.7 or < -0.7)
            for i in range(len(numeric_cols)):
                for j in range(i + 1, len(numeric_cols)):
                    corr_value = corr_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:
                        relationships.append({
                            "type": "correlation",
                            "column1": numeric_cols[i],
                            "column2": numeric_cols[j],
                            "strength": float(corr_value)
                        })
        
        # Limit relationships to avoid token bloat
        return relationships[:20]
    
    def _infer_python_type(self, series: pd.Series) -> str:
        """Infer the best Python type for a series."""
        if pd.api.types.is_integer_dtype(series):
            return "int"
        elif pd.api.types.is_float_dtype(series):
            return "float"
        elif pd.api.types.is_bool_dtype(series):
            return "bool"
        elif pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        else:
            return "str"
    
    def _get_fingerprint(self) -> str:
        """
        Generate a unique fingerprint for this dataset.
        Useful for caching and version tracking.
        """
        # Create a hash from column names and shape
        data = f"{list(self.df.columns)}_{self.df.shape}".encode()
        return hashlib.md5(data).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Return the complete passport as a dictionary."""
        return self.passport
    
    def to_prompt_context(self) -> str:
        """
        Convert passport to a compact string suitable for LLM prompts.
        This is what gets sent to the LLM instead of raw data.
        """
        context = f"""
# Dataset Information

## Shape
- Rows: {self.passport['metadata']['shape']['rows']:,}
- Columns: {self.passport['metadata']['shape']['columns']:,}
- Memory: {self.passport['metadata']['memory_usage_mb']:.2f} MB

## Column Schema
"""
        
        for col in self.passport['schema']:
            context += f"\n### {col['name']}\n"
            context += f"- Type: {col['dtype']} ({col['category']})\n"
            context += f"- Nulls: {col['null_count']:,} ({col['null_percentage']:.1f}%)\n"
            context += f"- Unique: {col['unique_count']:,}\n"
            
            if 'statistics' in col and 'error' not in col['statistics']:
                if col['category'] == 'numeric':
                    stats = col['statistics']
                    context += f"- Range: [{stats['min']:.2f}, {stats['max']:.2f}]\n"
                    context += f"- Mean: {stats['mean']:.2f}, Median: {stats['median']:.2f}\n"
                elif col['category'] == 'categorical':
                    stats = col['statistics']
                    context += f"- Most common: '{stats['most_common']}' ({stats['most_common_count']} times)\n"
        
        context += f"\n## Sample Data (first {self.passport['sample_data']['count']} rows)\n"
        context += f"{pd.DataFrame(self.passport['sample_data']['rows']).to_string()}\n"
        
        if self.passport['data_quality']['issues_count'] > 0:
            context += f"\n## Data Quality Issues ({self.passport['data_quality']['issues_count']} found)\n"
            for issue in self.passport['data_quality']['issues'][:5]:
                context += f"- {issue['column']}: {issue['issue']}\n"
        
        return context
    
    def get_column_descriptions(self) -> Dict[str, str]:
        """
        Get natural language descriptions of each column.
        Used for vector embedding in RAG system.
        """
        descriptions = {}
        
        for col in self.passport['schema']:
            desc_parts = [
                f"Column name: {col['name']}",
                f"Data type: {col['category']}",
            ]
            
            if 'statistics' in col and 'error' not in col['statistics']:
                if col['category'] == 'numeric':
                    stats = col['statistics']
                    desc_parts.append(f"Range from {stats['min']} to {stats['max']}")
                    desc_parts.append(f"Average value: {stats['mean']:.2f}")
                elif col['category'] == 'categorical':
                    stats = col['statistics']
                    desc_parts.append(f"Contains {col['unique_count']} unique values")
                    desc_parts.append(f"Most common value: {stats.get('most_common', 'N/A')}")
            
            descriptions[col['name']] = ". ".join(desc_parts)
        
        return descriptions


def generate_data_passport(df: pd.DataFrame, max_sample_rows: int = 5) -> DataPassport:
    """
    Convenience function to generate a data passport.
    
    Args:
        df: DataFrame to analyze
        max_sample_rows: Number of sample rows to include
        
    Returns:
        DataPassport object
    """
    return DataPassport(df, max_sample_rows)
