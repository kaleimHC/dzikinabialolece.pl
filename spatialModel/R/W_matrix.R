###############
### tessW() ###
###############
#
#' @title Contiguity spatial weight matrix for point data based on Voronoi tesselation titles
#'
#' @description
#' The function constructs the alternative spatial weight matrix W for point data. It first performs the Voronoi tesselation
#' and divides the area of the region into tiles, where points are the centroids of these tiles. Based on the newly created polygons,
#' it constructs the contiguity matrix W.
#'
#' @details
#' The function starts with the tesselation of the point pattern using the [sf::st_voronoi()] function, and based on these polygons,
#' creates the spatial weight matrix W using the [spdep::poly2nb()] and [spdep::nb2listw()] functions.
#'
#' @name tessW
#' @param points_sf Geo-located points in `sf` or the `data.frame` class - in the case of a `data.frame` object, the first and second columns must contain X and Y coordinates.
#' For `data.frame`, make sure that the coordinates of the points are in the same coordinate system / projection as the `region_sf` object.
#' @param region_sf Polygon in the `sf` class that defines the boundary for `points_sf`.
#' @param sample_size The sample size, must be less than or equal to the number of points in the dataset (`points_sf` parameter). If `sample_size` is greater, it is automatically set
#' to the number of points in the dataset.
#'
#' @return `tessW()` returns the contiguity matrix and a visualisation of the contiguity links between the points/tiles.
#'
#' ***Will be available soon***: In addition, if the value of `sample_size` is less than the number of observations in the dataset, the function will return which observations were used in the modelling.
#'
#' @examples
#' # Example of how tessW() works on a random subsample
#' my.tess<-tessW(firms_sf, region_sf, sample_size=50)
#' my.tess
#'
#' # tesselated W on a predefined dataset
#' subfirms_sf<-firms_sf[1:100,]
#' my.tess<-tessW(subfirms_sf, region_sf, sample_size=nrow(subfirms_sf))
#' my.tess
#'
#' @export
tessW<-function(points_sf, region_sf, sample_size){
  #sprawdzić czy warunek na typ jest ok?
  if(!inherits(region_sf,"sf")) {
    stop("The class of region_sf must only be 'sf'.\n")
  } else if(!(st_geometry_type(region_sf,FALSE)=="MULTIPOLYGON" || st_geometry_type(region_sf,FALSE)=="POLYGON")){
    stop("The type of region_sf must only be 'MULTIPOLYGON' or 'POLYGON'.")
  }

  # w przypadku gdy oba obiekty są typu sf uzgodnić ich system współrzędnych / projekcję(!!!)
  #Ew. do sprawdzenia czy warunek st_geometry_type(points_sf,FALSE)=="POINT") nie jest zbyt restrykcyjny
  if((inherits(points_sf,"sf") && st_geometry_type(points_sf,FALSE)=="POINT")) {
    # to można uprościć (trochę niepotrzebne wyjęcie współrzędnych i ich przerobienie ponownie), ale na razie zostawimy
    crds<-as.data.frame(st_coordinates(points_sf))
    colnames(crds)<-c("X_coord","Y_coord")
    crds_sf<-st_as_sf(crds,coords = c("X_coord","Y_coord"), crs=st_crs(points_sf), agr="constant")
    if (st_crs(points_sf)!=st_crs(region_sf)) {
      # sprawdzić czy działa przekształcenie
      crds_sf<-st_transform(crds_sf,crs=st_crs(region_sf))
      cat("The coordinates for point_sf object of class type data.frame have been tranformed to a geographic coordinate",
        "system / projection that matches the projection of the region_sf object: EPSG:",st_crs(region_sf)$epsg,".\n",sep="")
    }
  } else if(inherits(points_sf,"data.frame",TRUE)==1){
    crds<-points_sf[,c(1,2)]
    colnames(crds)<-c("X_coord","Y_coord")
    crds_sf<-st_as_sf(crds,coords = c("X_coord","Y_coord"), crs=st_crs(region_sf), agr="constant")
    cat("The coordinates from the point_sf object of class type data.frame have been assigned ",
      "a geographic coordinate system / projection that matches the projection of the region_sf object: EPSG:", st_crs(region_sf)$epsg,".\n",sep="")
  } else {
    stop("The class of points_sf must only be 'sf' of geometry type 'POINTS' or 'data.frame'.")
    }

  # zbadać sample_size i ustawić ew. na wielkość zbioru danych (może potem zmienić, żeby )
  sample_size <- as.integer(sample_size)
  if (sample_size > nrow(points_sf) || sample_size<1) {
    sample_size<-nrow(points_sf)
    cat("Wrong sample size. Sample_size set to:",sample_size,"\n",sep="")
  }

  # przekształcenie do EPSG:3857 zrobić może wcześniej (bo tesselacja lepiej działa w tym układzie - spr?)
  # zmniejszyć liczbę przekształceń
  crds_sf<-st_transform(crds_sf,crs=3857)
  region_sf<-st_transform(region_sf,crs=3857)

  # sample do testowania
  crds_sf_s<-crds_sf[sample(nrow(crds), sample_size, replace=FALSE), ]

  # tesselation - poprawić obiekty (może uprościć)
  crds_sfc_s<-st_geometry(crds_sf_s)
  region_sfc<-st_geometry(region_sf)
  crds_sfc_s_union<-st_union(crds_sfc_s)
  tess_result<-st_voronoi(crds_sfc_s_union, region_sfc)
  tess_result<-st_intersection(st_cast(tess_result), st_union(region_sfc))

  # macierz wag na bazie tesselowanych obszarów
  tess_result.nb<- poly2nb(tess_result)				# class nb
  tess_result.listw<-nb2listw(tess_result.nb, style="W")		# class listw

  crdsW.sf<-st_centroid(st_geometry(tess_result)) 	# centroidy / centroids

  # plot with points in blue
  par(mar=c(4,4,4,4))
  plot(st_geometry(tess_result), main="Weighting matrix based on a sample of point data.\n Regions determined by the tessellation method.")
  plot(tess_result.nb, crdsW.sf, add=TRUE)

  return(tess_result.listw)

}

###############
### bestW() ###
###############
#
#' @title Best number of k nearest neighbours (knn) to construct a spatial weight matrix for point data
#'
#' @description
#' Function calculates a set of candidate spatial econometric models on point data. The K nearest neighbours included in the
#' spatial weight matrix are specified in a user-specified vector. For the same equation, the function calculates models using
#' different spatial weight matrices and compares the AIC (Akaike Information Criterion). The model with the lowest AIC
#' is selected as the best. The function outputs the spatial weight matrix W for the best model and the number of knn used in the best W.
#'
#' @details
#' Function in an iterative quality check of spatial models that differ only in the number of nearest neighbours used to construct
#' the spatial weight matrix W. According to the study by Kubara & Kopczewska (2023), the AIC of such a set of models is a non-linear function
#' with a clear minimum. This function searches among the models for the lowest AIC and the underlying structure of the neighbourhood -
#' this is the best W. The function reports two line plots: AIC and spatial parameter (rho or lambda), both depending on knn,
#' and returns the best spatial weight matrix W.
#'
#' The function may run into computational problems on large data, which is typical of all spatial functions. The `sample_size` option allows
#' to set a smaller number of observations than in the original dataset to speed up the computation. If `sample_size` is equal to (or greater than)
#' the size of the dataset, all observations will be used.
#'
#' @name bestW
#' @param points_sf Geo-located points in `sf` or the `data.frame` class - in the case of a `data.frame` object, the first and second columns must contain X and Y coordinates.
#' @param eq An object that defines the equation for the model, can be in the [stats::formula()] class (or one that can be coerced to that class) or
#' a symbolic description of the model to be used.
#' @param model_type The type of spatial econometric model, one of "SAR", "SDM", "SEM", "SDEM", "SAC". The default is "SDM".
#' @param sample_size The sample size, must be less than or equal to the number of points in the dataset (`points_sf` parameter). If `sample_size` is greater, it is automatically set
#' to the number of points in the dataset.
#' @param knn The vector of alternative k nearest neighbours used in the subsequent spatial econometric models for the spatial weight matrix.
#'
#' @return `bestW()` returns a spatial weight matrix that minimises the AIC of the models for the given equation.
#' It defines the best number of knn. It displays two line plots with AIC and spatial parameter (rho or lambda),
#' both depending on the user-defined knn.
#'
#' ***Will be available soon***: In addition, if the value of `sample_size` is less than the number of observations in the dataset, the function will return which observations were used in the modelling.
#'
#' @references
#' Kubara, M., & Kopczewska, K. (2023). Akaike information criterion in choosing the optimal k-nearest neighbours of the spatial weight matrix.
#' Spatial Economic Analysis, 1-19.
#'
#' @examples
#' # The form of the equation to be estimated:
#' # Companies' return on assets (ROA) depends on their size, sector and relative location.
#' eq<-roa~empl+dummy.prod+dummy.constr+dummy.serv+dist.big.city
#' best.W<-bestW(firms_sf, eq, model_type="SDM", 1000, knn=c(2,5,10,15,20))
#' best.W
#'
#' @export
bestW<-function(points_sf, eq, model_type="SDM", sample_size, knn){
  #Ew. do sprawdzenia czy warunek st_geometry_type(data_sf,FALSE)=="POINT") nie jest zbyt restrykcyjny
  if((inherits(points_sf,"sf") && st_geometry_type(points_sf,FALSE)=="POINT")) {
    crds<-as.data.frame(st_coordinates(points_sf))
    colnames(crds)<-c("X_coord","Y_coord")
    cat("Points_sf was detected as an object of class sf.\n", sep = "")
  }  else if(inherits(points_sf,"data.frame",TRUE)==1){
    crds<-points_sf[,c(1,2)]
    colnames(crds)<-c("X_coord","Y_coord")
    cat("Points_sf was detected as an object of class data.frame.\n", sep = "")
  }  else {
    stop("The class of data_sf must only be 'sf' of geometry type 'POINTS' or 'data.frame'.")
  }

  # zbadać sample_size i ustawić ew. na wielkość zbioru danych (może potem zmienić, żeby )
  sample_size <- as.integer(sample_size)
  if (sample_size > nrow(points_sf) || sample_size<1) {
    sample_size<-nrow(points_sf)
    cat("Wrong sample size. Sample_size set to:",sample_size,"\n",sep="")
  }

  var_names<-all.vars(eq)
  m <- match(gsub(" ", ".", var_names), colnames(points_sf))
  if (any(is.na(m))) {
    stop("Variable names in eq are incorrect.")
  }

  # zbadać model_type - jeśli nie ma lub nie istnieje w danych, to pominąć, jeśli istnieje to wyciągnąć kolumnę
  if (length(model_type)>1) {
    model_type<-model_type[1]
    cat("Parameter model_type longer than 1. The first element has been selected: ",model_type,"\n",sep="")
  }

  if (!(model_type %in% c("SAR","SDM","SEM","SDEM","SAC"))) {
    stop("Unknown model type. Must be one of: SAR, SDM, SEM, SDEM, SAC.")
  }

  # knn - warunek
  if(!(is.numeric(knn))) {
    stop("knn is to be a numerical vector.")
  } else if (length(knn)<=1) {
    stop("knn should be a vector with a length greater than 1.")
  } else {
    knn<-sort(round(knn))
  }

  # sample do testowania
  selector<-sample(nrow(points_sf), sample_size, replace=FALSE)
  points_sf_s<-points_sf[selector,]
  crds_s<-crds[selector, ]
  crds_s[,1]<-crds_s[,1]+rnorm(sample_size, 0, sd(crds_s[,1])/1000)
  crds_s[,2]<-crds_s[,2]+rnorm(sample_size, 0, sd(crds_s[,2])/1000)

  # macierz rezultatów
  result<-matrix(NA, nrow=length(knn), ncol=4)
  colnames(result)<-c("knn", "AIC", "rho", "lambda")
  result[,1]<-knn

  if (model_type=="SAR") {
    cat(length(knn), " ",model_type, " models will be computed. ",
        "It can take a long while.","\n",sep="")
    for(i in 1:length(knn)){
      knnW_temp<-nb2listw(make.sym.nb(knn2nb(knearneigh(as.matrix(crds_s), k=knn[i]))))
      model_temp<-lagsarlm(eq, data=points_sf_s, knnW_temp)
      result[i,2]<-AIC(model_temp)
      result[i,3]<-model_temp$rho
      cat(i,"/",length(knn)," done.\n",sep="")
    }

  } else if (model_type=="SDM") {
    cat(length(knn), " ",model_type, " models will be computed. ",
        "It can take a long while.","\n",sep="")
    for(i in 1:length(knn)){
      knnW_temp<-nb2listw(make.sym.nb(knn2nb(knearneigh(as.matrix(crds_s), k=knn[i]))))
      model_temp<-lagsarlm(eq, data=points_sf_s, knnW_temp, type="mixed")
      result[i,2]<-AIC(model_temp)
      result[i,3]<-model_temp$rho
      cat(i,"/",length(knn)," done.\n",sep="")
    }

  } else if (model_type=="SEM") {
    cat(length(knn), " ",model_type, " models will be computed. ",
        "It can take a long while.","\n",sep="")
    for(i in 1:length(knn)){
      knnW_temp<-nb2listw(make.sym.nb(knn2nb(knearneigh(as.matrix(crds_s), k=knn[i]))))
      model_temp<-errorsarlm(eq, data=points_sf_s, knnW_temp)
      result[i,2]<-AIC(model_temp)
      result[i,4]<-model_temp$lambda
      cat(i,"/",length(knn)," done.\n",sep="")
    }

  } else if (model_type=="SDEM") {
    cat(length(knn), " ",model_type, " models will be computed. ",
        "It can take a long while.","\n",sep="")
    for(i in 1:length(knn)){
      knnW_temp<-nb2listw(make.sym.nb(knn2nb(knearneigh(as.matrix(crds_s), k=knn[i]))))
      model_temp<-errorsarlm(eq, data=points_sf_s, knnW_temp, etype="emixed")
      result[i,2]<-AIC(model_temp)
      result[i,4]<-model_temp$lambda
      cat(i,"/",length(knn)," done.\n",sep="")
    }

  } else if (model_type=="SAC") {
    cat(length(knn), " ",model_type, " models will be computed. ",
        "It can take a long while.","\n",sep="")
    for(i in 1:length(knn)){
      knnW_temp<-nb2listw(make.sym.nb(knn2nb(knearneigh(as.matrix(crds_s), k=knn[i]))))
      model_temp<-sacsarlm(eq, data=points_sf_s, knnW_temp)
      result[i,2]<-AIC(model_temp)
      result[i,3]<-model_temp$rho
      result[i,4]<-model_temp$lambda
      cat(i,"/",length(knn)," done.\n",sep="")
    }

  }

  result<-as.data.frame(result) # zostawiona obie kolumny rho i lambda - nieużywana w danym modelu z NA
  best.result<-result[result$AIC==min(result$AIC),]
  bestW.result<-nb2listw(make.sym.nb(knn2nb(knearneigh(as.matrix(crds_s), k=best.result[1]))))

  # jak idzie SAR lub SDM to rho, jak SEM lub SDEM to lambda,
  # a jak SAC to rho i lambda

  # można spróbować w pętli zapamiętywać najlepszą macierz bestW.result, żeby jej nie liczyć.
  # czy bestW.result do też jako OUTPUT? - będzie ciężko razem z df? bo trzeba to jako listę.

  if (model_type=="SAR" || model_type=="SDM") {
    par(mar=c(4,4,3,3), mfrow=c(1,2))
    # rysunek AIC w zależności od knn
    plot(result[,1:2], type="l", xlab="knn", ylab="AIC", lwd=2, cex.lab=0.9, cex.main=1,
         main="AIC value for the selected model depending on knn")
    points(result[,1:2], pch=21, bg="lightblue", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], max(result$AIC, na.rm=TRUE), paste("best knn:", best.result[1]))

    # rysunek rho w zależności od knn
    plot(result[,c(1,3)], type="l", xlab="knn", ylab="rho", lwd=2, cex.lab=0.9, cex.main=1,
         main="Rho for different knn")
    points(result[,c(1,3)], pch=21, bg="coral2", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], min(result$rho, na.rm=TRUE), "rho for best knn")

  } else if (model_type=="SEM" || model_type=="SDEM") {
    par(mar=c(4,4,3,3), mfrow=c(1,2))
    # rysunek AIC w zależności od knn
    plot(result[,1:2], type="l", xlab="knn", ylab="AIC", lwd=2, cex.lab=0.9, cex.main=1,
         main="AIC value for the selected model depending on knn")
    points(result[,1:2], pch=21, bg="lightblue", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], max(result$AIC, na.rm=TRUE), paste("best knn:", best.result[1]))

    # rysunek lambda w zależności od knn
    plot(result[,c(1,4)], type="l", xlab="knn", ylab="lambda", lwd=2, cex.lab=0.9, cex.main=1,
         main="Lambda for different knn")
    points(result[,c(1,4)], pch=21, bg="seagreen3", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], min(result$lambda, na.rm=TRUE), "lambda for best knn")

  } else if (model_type=="SAC") {
    par(mar=c(4,4,3,3), mfrow=c(1,3))
    # rysunek AIC w zależności od knn
    plot(result[,1:2], type="l", xlab="knn", ylab="AIC", lwd=2, cex.lab=0.9, cex.main=1,
         main="AIC value for the selected model depending on knn")
    points(result[,1:2], pch=21, bg="lightblue", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], max(result$AIC, na.rm=TRUE), paste("best knn:", best.result[1]))

    # rysunek rho w zależności od knn
    plot(result[,c(1,3)], type="l", xlab="knn", ylab="rho", lwd=2, cex.lab=0.9, cex.main=1,
         main="Rho for different knn")
    points(result[,c(1,3)], pch=21, bg="coral2", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], min(result$rho, na.rm=TRUE), "rho for best knn")

    # rysunek lambda w zależności od knn
    plot(result[,c(1,4)], type="l", xlab="knn", ylab="lambda", lwd=2, cex.lab=0.9, cex.main=1,
         main="Lambda for different knn")
    points(result[,c(1,4)], pch=21, bg="seagreen3", cex=1.5)
    abline(v=best.result[1], lty=3, col="grey60")
    text(best.result[1], min(result$lambda, na.rm=TRUE), "lambda for best knn")
  }

  par(mar=c(5.1,4.1,4.1,2.1), mfrow=c(1,1))

  return(result)
}

#########################
### corrSpatialLags() ###
#########################
#
#' @title Empirical and theoretical correlations between spatial lags with different numbers of k nearest neighbours in the spatial weight matrix W
#'
#' @description
#' Spatial lags calculated using different numbers of k nearest neighbours are correlated - strongly when the values of knn are similar,
#' and weakly when they are different. LeSage & Pace (2014) gave the formula for theoretical correlations between these lags.
#' The function reports two types of correlations: theoretical, as given by LeSage & Pace (2014), and empirical, using the Pearson
#' correlation coefficient applied to real values. It can be used to select the appropriate number of k nearest neighbours to be included
#' in spatial weights matrix for a point pattern.
#'
#' @details
#' Theoretical correlation between spatial lags calculated at different nearest neighbours equals (mi/mj)^0.5 where mi<mj
#' are the number of nearest neighbours.
#'
#' Empirical correlation uses Pearson correlation coefficient to determine observed correlations between spatial lags derived for
#' the same variable and different number of k nearest neighbours.
#'
#' @name corrSpatialLags
#' @param points_sf Geo-located points in `sf` or the `data.frame` class - in the case of a `data.frame` object, the first and second columns must contain X and Y coordinates.
#' @param var_name Name of the column (as text) in `points_sf` dataset with the variable to be analysed, e.g. "variable".
#' @param sample_size The sample size, must be less than or equal to the number of points in the dataset (`points_sf` parameter). If `sample_size` is greater, it is automatically set
#' to the number of points in the dataset.
#' @param knn The vector of alternative k nearest neighbours used in the subsequent spatial econometric models for the spatial weight matrix.
#'
#' @return `corrSpatialLags()` returns theoretical and empirical correlation matrices as numerical tables and coloured plot matrix.
#'
#' @references
#' Kubara, M., & Kopczewska, K. (2023). Akaike information criterion in choosing the optimal k-nearest neighbours of the spatial weight matrix.
#' Spatial Economic Analysis, 1-19.
#'
#' LeSage, J. P., & Pace, R. K. (2014). The biggest myth in spatial econometrics. Econometrics, 2(4), 217-249.
#'
#' @examples
#' csl<-corrSpatialLags(firms_sf, "roa", 500, knn=1:30)
#' csl
#'
#' @export
corrSpatialLags<-function(points_sf, var_name, sample_size, knn){
  #Ew. do sprawdzenia czy warunek st_geometry_type(data_sf,FALSE)=="POINT") nie jest zbyt restrykcyjny
  if((inherits(points_sf,"sf") && st_geometry_type(points_sf,FALSE)=="POINT")) {
    crds<-as.data.frame(st_coordinates(points_sf))
    colnames(crds)<-c("X_coord","Y_coord")
    cat("Points_sf was detected as an object of class sf.\n", sep = "")
  }  else if(inherits(points_sf,"data.frame",TRUE)==1){
    crds<-points_sf[,c(1,2)]
    colnames(crds)<-c("X_coord","Y_coord")
    cat("Points_sf was detected as an object of class data.frame.\n", sep = "")
  }  else {
    stop("The class of data_sf must only be 'sf' of geometry type 'POINTS' or 'data.frame'.")
  }

  # zbadać sample_size i ustawić ew. na wielkość zbioru danych (może potem zmienić, żeby )
  sample_size <- as.integer(sample_size)
  if (sample_size > nrow(points_sf) || sample_size<1) {
    sample_size<-nrow(points_sf)
