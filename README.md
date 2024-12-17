# BetaVAEImputation

As missing values are frequently present in genomic data, practical methods to handle missing data are necessary for downstream analyses that require complete datasets. In this work, we describe the use of a deep learning framework based on the variational autoencoder (VAE) to impute missing values in transcriptome and methylome data analysis.

The scripts contained in this repository can be used to carry out the analysis in “Genomic data imputation with variational autoencoders”. The data used in the manuscript is publicly accessible. Gene expression data is version 2 of the adjusted pan-cancer gene expression data obtained from Synapse: https://www.synapse.org/#!Synapse:syn4976369.2. DNA methylation data is the WGBS data for BLUEPRINT methylomes (2016 release) obtained from rnbeads.org: https://www.rnbeads.org/methylomes.html. Examples of preprocessing the raw data and creating missing value simulations can be found in ./preprocess.

**Imputation**

1. **VAE imputation**  
   ```bash
   python train_beta_VAE.py --config example_config_VAE.json
   python test_beta_VAE.py --config example_config_VAE.json
   ``` 
2. KNN imputation  
   ```bash
   python test_KNN.py --config example_config_KNN.json
   ```
3. SVD imputation
   ```bash
   python test_SVD.py --config example_config_SVD.json
   ```

**Compare clinical correlations**

1. Spearman correlation to histologic grade  
   ```bash
   python cindex_spearman_cor.py
   ```
   
2. Cox regression coefficient to survival
   ```bash
   Rscript find_cox_coeff.R  
   python cindex_cox_coeff.py
   ```
