*$ CREATE SOURCE.FOR
*COPY SOURCE
*
*=== source ===========================================================*
*
      SUBROUTINE SOURCE ( NOMORE )

      INCLUDE '(DBLPRC)'
      INCLUDE '(DIMPAR)'
      INCLUDE '(IOUNIT)'
*
*----------------------------------------------------------------------*
*  Watt fission spectrum (U-235), emitted radially outward from a      *
*  thin spherical shell r = 10.001 cm. Replicates the PHITS [Source]   *
*  block: s-type=9, dir=1, e-type=5, eg1=0.01, eg2=15.0 MeV,           *
*  f(E) = exp(-E/c1)*sinh(sqrt(c2*E)), c1=0.988, c2=2.249 (MeV).       *
*  Structure follows the standard FLUKA SOURCE routine template.       *
*----------------------------------------------------------------------*
*
      INCLUDE '(BEAMCM)'
      INCLUDE '(FHEAVY)'
      INCLUDE '(FLKSTK)'
      INCLUDE '(LTCLCM)'
      INCLUDE '(PAPROP)'
      INCLUDE '(SOURCM)'
      INCLUDE '(SUMCOU)'
*
      LOGICAL LFIRST
      SAVE LFIRST
      DATA LFIRST / .TRUE. /
*
      DOUBLE PRECISION C1, C2, EMINW, EMAXW, FMAX, RSRC, DUMMY
      PARAMETER ( C1    = 0.988D+00, C2    = 2.249D+00 )
      PARAMETER ( EMINW = 0.01D+00,  EMAXW = 15.0D+00  )
      PARAMETER ( FMAX  = 0.80D+00,  RSRC  = 10.001D+00 )
*
      NOMORE = 0
      TKESUM = ZERZER
      IF ( LFIRST ) THEN
         LFIRST = .FALSE.
      END IF
*
      NPFLKA = NPFLKA + 1
      IONID  = 8
      ILOFLK (NPFLKA) = IONID
      NPARMA = NPARMA + 1
      NUMPAR (NPFLKA) = NPARMA
      NEVENT (NPFLKA) = 0
      DFNEAR (NPFLKA) = +ZERZER
      AGESTK (NPFLKA) = +ZERZER
      AKNSHR (NPFLKA) = -TWOTWO
      IGROUP (NPFLKA) = 0
*
*  --- sample the Watt fission energy (rejection method) ---
  100 CONTINUE
      XI1 = FLRNDM (DUMMY)
      ENEMEV = EMINW + XI1 * ( EMAXW - EMINW )
      XI2 = FLRNDM (DUMMY)
      WATTF  = EXP(-ENEMEV/C1) * SINH(SQRT(C2*ENEMEV))
      IF ( XI2 * FMAX .GT. WATTF ) GO TO 100
      TKEFLK (NPFLKA) = ENEMEV * EMVGEV
      PMOFLK (NPFLKA) = SQRT ( TKEFLK (NPFLKA) * ( TKEFLK (NPFLKA)
     &                + TWOTWO * AM (IONID) ) )
*
*  --- isotropic point on shell r=RSRC ; direction = outward normal ---
      XI1 = FLRNDM (DUMMY)
      COSTH = TWOTWO * XI1 - ONEONE
      SINTH = SQRT ( MAX (ZERZER, ONEONE - COSTH*COSTH) )
      XI2 = FLRNDM (DUMMY)
      PHIAN = TWOTWO * PIPIPI * XI2
      XFLK  (NPFLKA) = RSRC * SINTH * COS(PHIAN)
      YFLK  (NPFLKA) = RSRC * SINTH * SIN(PHIAN)
      ZFLK  (NPFLKA) = RSRC * COSTH
      TXFLK (NPFLKA) = XFLK (NPFLKA) / RSRC
      TYFLK (NPFLKA) = YFLK (NPFLKA) / RSRC
      TZFLK (NPFLKA) = ZFLK (NPFLKA) / RSRC
*
      TXPOL (NPFLKA) = -TWOTWO
      TYPOL (NPFLKA) = +ZERZER
      TZPOL (NPFLKA) = +ZERZER
*
      WTFLK (NPFLKA) = ONEONE
      WEIPRI = WEIPRI + WTFLK (NPFLKA)
      LOFLK (NPFLKA) = 1
      LOUSE (NPFLKA) = 0
      DO 200 ISPR = 1, MKBMX1
         SPAREK (ISPR,NPFLKA) = ZERZER
  200 CONTINUE
      DO 300 ISPR = 1, MKBMX2
         ISPARK (ISPR,NPFLKA) = 0
  300 CONTINUE
      ISPARK (MKBMX2,NPFLKA) = NPFLKA
*
      TKESUM = TKESUM + TKEFLK (NPFLKA) * WTFLK (NPFLKA)
      LRADDC (NPFLKA) = .FALSE.
      RADDLY (NPFLKA) = ZERZER
*
      CALL GEODRR ( TXFLK (NPFLKA), TYFLK (NPFLKA), TZFLK (NPFLKA) )
      CALL GEOREG ( XFLK (NPFLKA), YFLK (NPFLKA), ZFLK (NPFLKA),
     &              NRGFLK(NPFLKA), IDISC )
      CALL GEOHSM ( NHSPNT (NPFLKA), 1, -11, MLATTC )
      NLATTC (NPFLKA) = MLATTC
      CMPATH (NPFLKA) = ZERZER
      CALL SOEVSV
      RETURN
*=== End of subroutine Source =========================================*
      END
